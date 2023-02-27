#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""  
Copyright (c) 2021 Software AG, Darmstadt, Germany and/or its licensors

SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import json
import re
import logging
from operator import contains
import time
import subprocess as sp
import pathlib
from os.path import expanduser

from c8ydm.core.apt_package_manager import AptPackageManager
from c8ydm.framework.modulebase import Initializer, Listener
from c8ydm.framework.smartrest import SmartRESTMessage
from c8ydm.utils import Configuration


class SoftwareManager(Listener, Initializer):        
    """ Software Update Module"""
    logger = logging.getLogger(__name__)
    apt_package_manager = AptPackageManager()        

    def __init__(self,serial, agent):
        super().__init__(serial, agent)
        home = expanduser('~')
        path = pathlib.Path(home + '/.cumulocity')
        config = Configuration(str(path))
        if config.getValue('software','packagemanager'):
            self.packagemanager = config.getValue('software','packagemanager')
        else:
            self.packagemanager="apt"

    def group(self, seq, sep):
        result = [[]]
        for e in seq:
            #logging.info("e: "+str(e) +" sep: " + str(sep))
            if sep not in str(e):
                result[-1].append(e)
            else:
                result[-1].append(e[:e.find(sep)])
                result.append([])

        if result[-1] == []:
            result.pop()  # thx iBug's comment
        return result
    
    def get_filename_from_cd(self, cd):
        """
        Get filename from content-disposition
        """
        if not cd:
            return None
        fname = re.findall('filename=(.+)', cd)
        if len(fname) == 0:
            return None
        return fname[0]

    def handleOperation(self, message):
        try:
            
            if 's/ds' in message.topic and message.messageId == '528':
                # Software Update without type
                messages = self.group(message.values, '\n')[0]
                deviceId = messages.pop(0)
                binary_included = False
                self.logger.info('Software update for device ' +
                                 deviceId + ' with message ' + str(messages))
                executing = SmartRESTMessage(
                    's/us', '501', ['c8y_SoftwareUpdate'])
                self.agent.publishMessage(executing)
                softwareToInstall = [messages[x:x + 4]
                                     for x in range(0, len(messages), 4)]
                for software in softwareToInstall:
                    name = software[0]
                    version = software[1]
                    url = software[2]
                    action = software[3]
                    if 'binaries' in url:
                        # File provided
                        binary_included = True
                if not binary_included:
                    [errors, software_installed] = self.apt_package_manager.install_software(
                        softwareToInstall, True, False)
                    self.logger.info('Finished all software update')
                    if len(errors) == 0:
                        # finished without errors
                        finished = SmartRESTMessage(
                            's/us', '503', ['c8y_SoftwareUpdate'])
                    else:
                        # finished with errors
                        finished = SmartRESTMessage(
                            's/us', '502', ['c8y_SoftwareUpdate', ' - '.join(errors)])
                    self.agent.publishMessage(finished)
                    if self.agent.token_received.wait(timeout=self.agent.refresh_token_interval):
                        installed_software = self.apt_package_manager.get_installed_software_json(False)
                        mo_id = self.agent.rest_client.get_internal_id(self.agent.serial)
                        self.agent.rest_client.update_managed_object(mo_id, json.dumps(installed_software))
                else:
                    # Binary included in software update
                    self.logger.info(f'Software Updated with provided file {url}')
                    file = self.agent.rest_client.download_c8y_binary(url)
                    self.logger.info(f'File to be installed: {file}')
                    if action == 'install' or action == 'update':
                        #result = sp.run(["dpkg","-i", file], stdout=sp.PIPE, stderr=sp.PIPE)
                        result = sp.run(["apt-get","-y","install",file], stdout=sp.PIPE, stderr=sp.PIPE)
                        errors = result.stderr.decode("utf-8")
                        self.logger.info(f'Result of subprocess Error: {errors}')
                        if errors:
                            failed = SmartRESTMessage('s/us', '502', ['c8y_SoftwareUpdate', errors])
                            self.agent.publishMessage(failed)
                        else:
                            finished = SmartRESTMessage(
                                's/us', '503', ['c8y_SoftwareUpdate'])
                            self.agent.publishMessage(finished)
                        if self.agent.token_received.wait(timeout=self.agent.refresh_token_interval):
                            installed_software = self.apt_package_manager.get_installed_software_json(False)
                            mo_id = self.agent.rest_client.get_internal_id(self.agent.serial)
                            self.agent.rest_client.update_managed_object(mo_id, json.dumps(installed_software))
                                

            if 's/ds' in message.topic and message.messageId == '529' and self.packagemanager=="apt":
                # Software Update with type
                # When multiple operations received just take the first one for further processing
                #self.logger.debug("message received :" + str(message.values))
                messages = self.group(message.values, '\n')[0]
                deviceId = messages.pop(0)
                binary_included = False
                self.logger.info('Software update for device ' +
                                 deviceId + ' with message ' + str(messages))
                executing = SmartRESTMessage(
                    's/us', '501', ['c8y_SoftwareUpdate'])
                self.agent.publishMessage(executing)
                softwareToInstall = [messages[x:x + 5]
                                     for x in range(0, len(messages), 5)]
                for software in softwareToInstall:
                    name = software[0]
                    version = software[1]
                    type = software[2]
                    url = software[3]
                    action = software[4]
                    if 'binaries' in url:
                        # File provided
                        binary_included = True
                if not binary_included:
                    [errors, software_installed] = self.apt_package_manager.install_software(
                        softwareToInstall, True, True)
                    for software in software_installed:
                        self.logger.info(f'Software processed: {software}')
                        action = software['action']
                        name = software['name']
                        type = software['type']
                        version = software['version']
                        if action == 'install' or action == 'update':
                            self.agent.publishMessage(SmartRESTMessage('s/us', '141', [name, version, type, 'test']))
                        if action == 'delete':
                            self.agent.publishMessage(SmartRESTMessage('s/us', '142', [name, version]))
                    self.logger.info('Finished all software update')
                    if len(errors) == 0:
                        # finished without errors
                        finished = SmartRESTMessage(
                            's/us', '503', ['c8y_SoftwareUpdate'])
                    else:
                        # finished with errors
                        finished = SmartRESTMessage(
                            's/us', '502', ['c8y_SoftwareUpdate', ' - '.join(errors)])
                    self.agent.publishMessage(finished)
                    #self.agent.publishMessage(
                    #    self.apt_package_manager.getInstalledSoftware(False))
                else:
                    # Binary included in software update
                    self.logger.info(f'Software Updated with provided file {url}')
                    file = self.agent.rest_client.download_c8y_binary(url)
                    self.logger.info(f'File to be installed: {file}')
                    if action == 'install' or action == 'update':
                        #result = sp.run(["dpkg","-i", file], stdout=sp.PIPE, stderr=sp.PIPE)
                        result = sp.run(["apt-get","-y","install",file], stdout=sp.PIPE, stderr=sp.PIPE)
                        errors = result.stderr.decode("utf-8")
                        self.logger.info(f'Result of subprocess Error: {errors}')
                        if errors:
                            failed = SmartRESTMessage('s/us', '502', ['c8y_SoftwareUpdate', errors])
                            self.agent.publishMessage(failed)
                        else:
                            finished = SmartRESTMessage(
                                's/us', '503', ['c8y_SoftwareUpdate'])
                            self.agent.publishMessage(SmartRESTMessage('s/us', '141', [name, version, type, '']))
                            self.agent.publishMessage(finished)
                            #self.agent.publishMessage(
                            #    self.apt_package_manager.getInstalledSoftware(False))
            
            if 's/ds' in message.topic and message.messageId == '529' and self.packagemanager=="snap":
                # Software Update with type
                # When multiple operations received just take the first one for further processing
                #self.logger.debug("message received :" + str(message.values))
                messages = self.group(message.values, '\n')[0]
                deviceId = messages.pop(0)
                binary_included = False
                self.logger.info('Software update for device ' +
                                 deviceId + ' with message ' + str(messages))
                executing = SmartRESTMessage(
                    's/us', '501', ['c8y_SoftwareUpdate'])
                self.agent.publishMessage(executing)
                softwareToInstall = [messages[x:x + 5]
                                     for x in range(0, len(messages), 5)]
                for software in softwareToInstall:
                    name = software[0]
                    version = software[1]
                    type = software[2]
                    url = software[3]
                    action = software[4]
                    if 'binaries' in url:
                        # File provided
                        binary_included = True
                installedSoftware = self.getFormatedSnaps()
                errors = self.installSnap(softwareToInstall)
                self.logger.debug("---------------------")
                self.logger.debug(f'Following packages are installed: {installedSoftware}')
                self.logger.debug(f'Type is: {type(installedSoftware)}')
                for software in installedSoftware:
                    self.logger.info(f'Software processed: {software}')
                    name = software
                    type = 'snap'
                    version = software[0]
                    if action == 'install' or action == 'update':
                        self.agent.publishMessage(SmartRESTMessage('s/us', '141', [name, version, type, 'test']))
                    if action == 'delete':
                        self.agent.publishMessage(SmartRESTMessage('s/us', '142', [name, version]))
                self.logger.info('Finished all software update')
                if len(errors) == 0:
                    # finished without errors
                    finished = SmartRESTMessage(
                        's/us', '503', ['c8y_SoftwareUpdate'])
                else:
                    # finished with errors
                    finished = SmartRESTMessage(
                        's/us', '502', ['c8y_SoftwareUpdate', ' - '.join(errors)])
                self.agent.publishMessage(finished)
                #self.agent.publishMessage(
                #    self.apt_package_manager.getInstalledSoftware(False))
                
                
            if 's/ds' in message.topic and message.messageId == '516' and self.packagemanager=="apt":
                # When multiple operations received just take the first one for further processing
                #self.logger.debug("message received :" + str(message.values))
                messages = self.group(message.values, '\n')[0]
                #self.logger.info("message processed:" + str(messages))
                deviceId = messages.pop(0)
                self.logger.info('Software update for device ' +
                                 deviceId + ' with message ' + str(messages))
                executing = SmartRESTMessage(
                    's/us', '501', ['c8y_SoftwareList'])
                self.agent.publishMessage(executing)
                softwareToInstall = [messages[x:x + 3]
                                     for x in range(0, len(messages), 3)]
                errors= self.apt_package_manager.installSoftware(
                    softwareToInstall, True)
                self.logger.info('Finished all software update')
                if len(errors) == 0:
                    # finished without errors
                    finished = SmartRESTMessage(
                        's/us', '503', ['c8y_SoftwareList'])
                else:
                    # finished with errors
                    finished = SmartRESTMessage(
                        's/us', '502', ['c8y_SoftwareList', ' - '.join(errors)])
                installed_software = self.apt_package_manager.get_installed_software_json(False)
                mo_id = self.agent.rest_client.get_internal_id(self.agent.serial)
                self.agent.rest_client.update_managed_object(mo_id, json.dumps(installed_software))
                self.agent.publishMessage(finished)
                self.agent.publishMessage(
                    self.apt_package_manager.getInstalledSoftware(False))
                
            if 's/ds' in message.topic and message.messageId == '516' and self.packagemanager=="snap":
                # When multiple operations received just take the first one for further processing
                #self.logger.debug("message received :" + str(message.values))
                messages = self.group(message.values, '\n')[0]
                #self.logger.info("message processed:" + str(messages))
                deviceId = messages.pop(0)
                self.logger.info('Software update for device ' +
                                 deviceId + ' with message ' + str(messages))
                executing = SmartRESTMessage(
                    's/us', '501', ['c8y_SoftwareList'])
                self.agent.publishMessage(executing)
                softwareToInstall = [messages[x:x + 3]
                                     for x in range(0, len(messages), 3)]
                if not self.agent.snapdClient.isBusy:
                    self.agent.snapdClient.isBusy = True
                    installedSoftware = self.getFormatedSnaps()
                    errors = self.installSnap(installedSoftware, softwareToInstall)
                    logging.info('Finished all software update')
                    if len(errors) == 0:
                        # finished without errors
                        finished = SmartRESTMessage('s/us', '503', ['c8y_SoftwareList'])
                    else:
                        # finished with errors
                        finished = SmartRESTMessage('s/us', '502', ['c8y_SoftwareList', ' - '.join(errors)])
                    self.agent.publishMessage(finished)
                    self.agent.publishMessage(self.getInstalledSnaps())
                    self.agent.snapdClient.isBusy = False
                else:
                    executing = SmartRESTMessage(
                    's/us', '502', ['c8y_SoftwareList','Snapd is busy'])
                self.agent.publishMessage(executing)
                self.logger.info('Finished all software update')
                if len(errors) == 0:
                    # finished without errors
                    finished = SmartRESTMessage(
                        's/us', '503', ['c8y_SoftwareList'])
                else:
                    # finished with errors
                    finished = SmartRESTMessage(
                        's/us', '502', ['c8y_SoftwareList', ' - '.join(errors)])
        except Exception as e:
            self.logger.exception(e)
            failed = SmartRESTMessage(
                's/us', '502', ['c8y_SoftwareList', str(e)])
            self.agent.publishMessage(failed)
            failed = SmartRESTMessage(
                's/us', '502', ['c8y_SoftwareUpdate', str(e)])
            self.agent.publishMessage(failed)

    def getSupportedOperations(self):
        if self.agent.token_received.wait(timeout=self.agent.refresh_token_interval):
            supported_sw_types = { 'c8y_SupportedSoftwareTypes': ['snap']}
            mo_id = self.agent.rest_client.get_internal_id(self.agent.serial)
            self.agent.rest_client.update_managed_object(mo_id, json.dumps(supported_sw_types))
        return ['c8y_SoftwareUpdate', 'c8y_SoftwareList']

    def getSupportedTemplates(self):
        return []

    def getMessages(self):
        if self.packagemanager == "apt": 
            installed_software = self.apt_package_manager.get_installed_software_json(False)
        elif self.packagemanager == "snap":
            installed_software = self.getInstalledSnaps()
        if self.agent.token_received.wait(timeout=self.agent.refresh_token_interval):
            mo_id = self.agent.rest_client.get_internal_id(self.agent.serial)
            #self.agent.rest_client.update_managed_object(mo_id, json.dumps(installed_software))
            self.agent.rest_client.set_adv_software_list(mo_id, installed_software)
        #return self.apt_package_manager.getInstalledSoftware(True)
        return None
    
    def getFormatedSnaps(self):
        snapd = self.agent.snapdClient
        installedSnaps = snapd.getInstalledSnaps()
        allInstalled = {}
        for snap in installedSnaps['result']:
            allInstalled[snap['name']] = {
                'version': snap['version'],
                'channel': snap['channel']
            }
        return allInstalled
    
    def getInstalledSnaps(self):
        snapd = self.agent.snapdClient
        installedSnaps = snapd.getInstalledSnaps()
        logging.debug(installedSnaps)
        allInstalled = []

        for snap in installedSnaps['result']:
            snapInfo = []
            # Name
            snapInfo.append(snap['name'])
            # Version
            snapInfo.append(snap['version'] + '##' + snap['channel'])
            # URL
            snapInfo.append('')
            allInstalled.extend(snapInfo)

        return SmartRESTMessage('s/us', '116', allInstalled)
    
    def installSnap(self, toBeInstalled):
        snapd = self.agent.snapdClient
        wantedSnaps = []
        errors = []
        for software in toBeInstalled:
            name = software[0]
            wantedSnaps.append(name)
            channel = software[1].split('##')[-1]
            toBeVersion = software[1].split('##')[0]
            action = software[4]
            if action == "install":
                # try install
                logging.info('Install snap "%s" with channel "%s"', name, channel)
                response = snapd.installSnap(name, channel)
                if response['status-code'] >= 400:
                    logging.error('Snap %s error: %s', name, response['result']['message'])
                    errors.append('Snap' + name + ' error: ' + response['result']['message'])
                elif response['status-code'] == 202:
                    changeId = response['change']
                    changeStatus = self.getChangeStatus(changeId)
                    while not changeStatus['finished']:
                        time.sleep(3)
                        changeStatus = self.getChangeStatus(changeId)
                    logging.debug('Finished snap ' + name)
                    if changeStatus['error']:
                        errors.append(changeStatus['error'])
            elif action == "update":
                # try update
                    logging.info('Update snap "%s" with channel "%s"', name, channel)
                    if name == 'c8ycc':
                        response = snapd.updateSnap(name, channel, devmode=True, classic=False)
                    else:
                        response = snapd.updateSnap(name, channel)
                    if response['status-code'] >= 400:
                        logging.error('Snap %s error: %s', name, response['result']['message'])
                        errors.append('Snap' + name + ' error: ' + response['result']['message'])
                    elif response['status-code'] == 202:
                        changeId = response['change']
                        changeStatus = self.getChangeStatus(changeId)
                        while not changeStatus['finished']:
                            time.sleep(3)
                            changeStatus = self.getChangeStatus(changeId)
                        logging.debug('Finished snap ' + name)
                        if changeStatus['error']:
                            errors.append(changeStatus['error'])
            elif action == "remove":
                pass
            else:
                pass
        return errors
    
    def getChangeStatus(self, changeId):
        snapd = self.agent.snapdClient
        changeStatus = snapd.getChangeStatus(changeId)
        error = None
        finished = changeStatus['result']['status'] == 'Done'
        if not finished and changeStatus['result']['status'] == 'Error':
            finished = True
            error = changeStatus['result']['err']
        return {
            'finished': finished,
            'error': error
        }
