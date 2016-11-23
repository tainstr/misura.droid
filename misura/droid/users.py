#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
from copy import deepcopy

from . import parameters as params
import device

# TODO: translate params variables into Users object options.


class Users(device.Device):

    """Gestione utenti e livelli di autorizzazione."""
    naturalName = 'users'
    conf_def = deepcopy(device.Device.conf_def)
    conf_def.append({"handle": u'users', "name": u'Users List', "type": 'Table',
                     "readLevel":5, "writeLevel":5,  "current": [
                         [('Name', 'String'), ('Read Level', 'Integer'),
                          ('Write Level', 'Integer'), ('Hash', 'String')],
                         ['admin', 5, 5, 'admin'],
                         ['maint', 4, 4, 'maint'],
                         ['tech', 3, 3, 'tech'],
                         ['user', 2, 2, 'user'],
                         ['analyst', 1, 1, 'analyst'],
                         ['guest', 0, 0, 'guest']
                     ]})

    def __init__(self, parent=None, node='users'):
        device.Device.__init__(self, parent=parent, node=node)
        self.name = 'users'
        self['name'] = 'Users'
        self['comment'] = 'Users Access Control'
        self['devpath'] = 'users'
        self.dic = {}
        self.set_users(self['users'])
        self.logged = [False, 0]
        self.xmlrpc_auth = self.auth
        self.post_connection()

    def set_users(self, val):
        self.dic = {ent[0]: [ent[1], ent[2], ent[3]] for ent in val[1:]}
        return val

    def auth(self, credentials):
        """Verify credentials"""
        user = credentials.username
        if user not in self.dic:
            msg = 'No such user: {}'.format(user)
            self.log.critical(msg)
            return False, msg
        rlev, wlev, pw = self.dic[user]
        if credentials.checkPassword(pw):
            return True, user
        msg = 'Wrong password for user: {}'.format(user)
        self.log.critical(msg)
        return False,  msg

    def levels(self, user):
        return self.dic[user][:2]

    def logout(self, userName=''):
        if self.logged[0] != userName:
            self.log.warning(
                'User asked to logout without being logged in: ', userName)
            return 'You were not logged in'
        self.logged = [False, 0]
        if params.exclusiveLogin:
            self.log.info('Successfull logout for user: ', userName)
            return 'Logout successfull.'
        else:
            msg = 'Exclusive login is not active. Logout is useless.'
            self.log.info(msg)
            return msg
    xmlrpc_logout = logout
