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
import logging, time
from c8ydm.framework.packagemanager import PackageManager
from c8ydm.framework.smartrest import SmartRESTMessage
from c8ydm.utils.snapd_client import SnapdClient


class SnapDPackageManager(PackageManager):
    logger = logging.getLogger(__name__)
    snapdClient = SnapdClient()

    def get_change_status(self, changeId):
        snapd = self.snapdClient
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

    def get_installed_software(self, with_update):
        snapd = self.snapdClient
        installedSnaps = snapd.getInstalledSnaps()
        logging.debug(installedSnaps)
        allInstalled = []
        for snap in installedSnaps['result']:
            snapInfo = []
            # Name
            snapInfo.append(snap['name'])
            # Version
            snapInfo.append(snap['version'] + ' - ' + snap['channel'])
            # Software Type
            snapInfo.append('snap')
            # URL
            snapInfo.append(' ')
            allInstalled.extend(snapInfo)
        return SmartRESTMessage('s/us', '140', allInstalled)
    
    def get_installed_software_json(self, with_update):
        software_list = []
        snapd = self.snapdClient
        installedSnaps = snapd.getInstalledSnaps()
        for snap in installedSnaps['result']:
            software = {
                        "name": snap['name'],
			            "version": snap['version'] + ' - ' + snap['channel'],
                        "softwareType": "snap",
			            "url": "test"
                    }
            software_list.append(software)
        return software_list

    def install_software(self, software_to_install, with_update):
            snapd = self.snapdClient
            wantedSnaps = []
            software_installed = []
            errors = []
            for software in software_to_install:
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
                    elif response['status-code'] == 202 or response['status-code']== 200 or response['status-code']  == 201:
                        changeId = response['change']
                        changeStatus = self.get_change_status(changeId)
                        while not changeStatus['finished']:
                            time.sleep(3)
                            changeStatus = self.get_change_status(changeId)
                        logging.debug('Finished snap ' + name)
                        software = {
                            "name": name,
                            "version": toBeVersion + ' - ' + channel,
                            "type": "snap",
                            "url": "",
                            "action": "install"
                        }
                        software_installed.append(software)
                        #self.agent.publishMessage(SmartRESTMessage('s/us', '141', [name, toBeVersion, 'version', ' ']))
                        if changeStatus['error']:
                            errors.append(changeStatus['error'])
                elif action == "update":
                    # try update
                        logging.info('Update snap "%s" with channel "%s"', name, channel)
                        response = snapd.updateSnap(name, channel)
                        if response['status-code'] >= 400:
                            logging.error('Snap %s error: %s', name, response['result']['message'])
                            errors.append('Snap' + name + ' error: ' + response['result']['message'])
                        elif response['status-code'] == 202 or response['status-code']== 200 or response['status-code']  == 201:
                            changeId = response['change']
                            changeStatus = self.get_change_status(changeId)
                            while not changeStatus['finished']:
                                time.sleep(3)
                                changeStatus = self.get_change_status(changeId)
                            logging.debug('Finished snap ' + name)
                            if changeStatus['error']:
                                errors.append(changeStatus['error'])
                elif action == "delete":
                    # try remove
                        logging.info('Remove snap "%s" with channel "%s"', name, channel)
                        response = snapd.deleteSnap(name)
                        if response['status-code'] >= 400:
                            logging.error('Snap %s error: %s', name, response['result']['message'])
                            errors.append('Snap' + name + ' error: ' + response['result']['message'])
                        elif response['status-code'] == 202 or response['status-code']== 200 or response['status-code']  == 201:
                            changeId = response['change']
                            changeStatus = self.get_change_status(changeId)
                            while not changeStatus['finished']:
                                time.sleep(3)
                                changeStatus = self.get_change_status(changeId)
                            logging.debug('Finished snap ' + name)
                            if changeStatus['error']:
                                errors.append(changeStatus['error'])
                else:
                    pass
            return errors

    def get_formated_snaps(self):
        snapd = self.snapdClient
        installedSnaps = snapd.getInstalledSnaps()
        allInstalled = {}
        for snap in installedSnaps['result']:
            allInstalled[snap['name']] = {
                'version': snap['version'],
                'channel': snap['channel'],
                'softwareType': 'snap',
                'url': ' '
            }
        return allInstalled
