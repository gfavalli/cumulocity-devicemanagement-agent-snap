#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests_unixsocket
import logging
import json, time


class SnapdClient():
    snapdSocket = 'http+unix://%2Frun%2Fsnapd.socket'
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.isBusy = False
        snapConnected = False
        while not snapConnected:
            try:
                self.logger.info('Trying to connect to snapd Socket...')
                self.session = requests_unixsocket.Session()
                self.logger.info('Successfully conncted to snapd Socket')
                snapConnected = True
            except Exception as e:
                self.logger.error('Connection to snapd could not be established')
                self.logger.exception(e)
                time.sleep(5)

    def getSystemInfo(self):
        try:
            response = self.session.get(self.snapdSocket + '/v2/system-info')
            return response.json()
        except Exception as e:
            self.logger.exception(e)

    def getInstalledSnaps(self):
        try:
            response = self.session.get(self.snapdSocket + '/v2/snaps')
            return response.json()
        except Exception as e:
            self.logger.exception(e)

    def restartSnap(self, snapName):
        body = {
            "action": "restart",
            "names": [snapName]
        }
        headers = {
            'Content-Type': 'application/json'
        }
        try:
            response = self.session.post(self.snapdSocket + '/v2/apps', data=json.dumps(body), headers=headers)
            return response.json()
        except Exception as e:
            self.logger.exception(e)

    def installSnap(self, snapName, snapChannel=None, devmode=False, classic=False):
        body = {
            'action': 'install'
        }
        headers = {
            'Content-Type': 'application/json'
        }
        if snapChannel:
            body['channel'] = snapChannel
        try:
            # response = self.session.post(self.snapdSocket + '/v2/snaps', data=json.dumps(body))
            response = self.session.post(self.snapdSocket + '/v2/snaps/' + snapName, data=json.dumps(body), headers=headers)
            return response.json()
        except Exception as e:
            self.logger.exception(e)

    def updateSnap(self, snapName, snapChannel=None, devmode=False, classic=False):
        body = {
            'action': 'refresh'
        }
        headers = {
            'Content-Type': 'application/json'
        }
        if snapChannel:
            body['channel'] = snapChannel
        if devmode:
            body['devmode'] = devmode
        try:
            response = self.session.post(self.snapdSocket + '/v2/snaps/' + snapName, data=json.dumps(body), headers=headers)
            return response.json()
        except Exception as e:
            self.logger.exception(e)

    def updateSnaps(self):
        body = {
            'action': 'refresh'
        }
        headers = {
            'Content-Type': 'application/json'
        }
        try:
            response = self.session.post(self.snapdSocket + '/v2/snaps', data=json.dumps(body), headers=headers)
            return response.json()
        except Exception as e:
           self.logger.exception(e)

    def deleteSnap(self, snapName):
        body = {
            'action': 'remove'
        }
        try:
            response = self.session.post(self.snapdSocket + '/v2/snaps/' + snapName, data=json.dumps(body))
            return response.json()
        except Exception as e:
            self.logger.exception(e)

    def revertSnap(self, snapName):
        body = {
            'action': 'revert'
        }
        try:
            response = self.session.post(self.snapdSocket + '/v2/snaps/' + snapName, data=json.dumps(body))
            return response.json()
        except Exception as e:
            self.logger.exception(e)

    def getChangeStatus(self, changeId):
        try:
            response = self.session.get(self.snapdSocket + '/v2/changes/' + changeId)
            return response.json()
        except Exception as e:
            self.logger.exception(e)
