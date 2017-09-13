#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
import os
from copy import deepcopy
import datetime
from commands import getstatusoutput as go
from . import parameters as params
import device
from misura.droid.version import __version__


def get_lib_info():
    """Find all libraries loaded in current process and their real shared object name with version"""
    r = go('pmap -p {}'.format(os.getpid()))
    paths = set([])
    out = ''
    for line in r[1].splitlines()[1:-1]:
        line = line.split(' ')
        p = line.pop(-1)
        if not p.startswith('/'):
            continue
        if not os.path.exists(p):
            continue
        if p in paths:
            continue
        paths.add(p)
        elf = go('readelf -d {}|grep SONAME'.format(p))[1]
        i = elf.find('[') + 1
        e = elf.find(']')
        out += '{} -> {}\n'.format(p, elf[i:e])
    return out

tar_log_limit = 1e6


class Support(device.Device):

    """Support functionalities. Backup/restore, upgrade, remote assistance."""
    naturalName = 'support'
    conf_def = deepcopy(device.Device.conf_def)
    conf_def += [
        # Conf Backups
        {"handle": 'stopUI', "name": 'Stop embedded UI', "current": False, "type": 'Boolean',"writeLevel":5},
        {"handle": u'backups', "name": u'Available backups',
            "type": 'FileList', 'attr': ['Runtime']},
        {"handle": u'doBackup', "name": u'New configuration backup',
            "type": 'Button', "parent": 'backups'},
        {"handle": u'doRestore', "name": u'Restore configuration backup',
            "type": 'Button', "parent": 'backups'},
        # Exe backups
        {"handle": u'exeBackups', "name": u'Available software backups',
            "type": 'FileList', 'attr': ['Runtime']},
        {"handle": u'doExeBackup', "name": u'New software backup',
            "type": 'Button', "parent": 'exeBackups'},
        {"handle": u'doExeRestore', "name": u'Restore software backup',
            "type": 'Button', "parent": 'exeBackups'},
        # Progress
        {"handle": u'backupProgress', "name": u'Backup/restore progress',
            "type": 'Progress', "attr": ['Runtime']},

        {"handle": u'packages', "name": u'Available software versions',
            "type": 'FileList', 'attr': ['Runtime']},
        {"handle": u'applyExe', "name": u'Apply selected software version',
            "type": 'Button', "parent": 'packages'},
        {"handle": u'upgrade', "name": u'Download new software version',
            "type": 'Button', "parent": 'packages'},
        {"handle": u'upgradeUrl', "name": u'Upgrade site',
            "type": 'String', "parent": 'packages'},
        {"handle": u'upgradeProgress', "name": u'Upgrade/restore progress',
            "type": 'Progress', "attr": ['Runtime']},

        # System info
        {"handle": u'version', "name": u'Misura version',
            "type": 'String', 'attr': ['ReadOnly']},
        {"handle": u'libs', "name": u'Loaded libraries info',
            "type": 'Button'},
        {"handle": u'env', "name": u'Environment variables', "type": 'Button'},

        # Network
        {"handle": u'network',
            "name": u'Apply network configuration', "type": 'Button'},
        {"handle": 'dhcp', "name": 'Autoconfigure with DHCP',
         "current": True, "type": 'Boolean', "parent": 'network'},
        {"handle": 'staticip', "name": 'Static IP',
            "type": 'String', "parent": 'network'},
        {"handle": 'netmask', "name": 'Static Netmask',
            "type": 'String', "parent": 'network'},
        {"handle": 'gateway', "name": 'Static Gateway',
            "type": 'String', "parent": 'network'},
        {"handle": u'reboot', "name": u'Reboot machine OS', "type": 'Button'},
        {"handle": u'halt', "name": u'Shutdown machine OS', "type": 'Button'},
        
    ]

    def __init__(self, parent=None, node='support'):
        device.Device.__init__(self, parent=parent, node=node)
        self.name = 'support'
        self['name'] = 'Support'
        self['comment'] = 'Support, upgrade, backup, restore, get assistance'
        self['devpath'] = 'support'
        self.post_connection()
        self.set_stopUI(self['stopUI'])

            
    def set_stopUI(self, val):
        if val:
            self.log.debug('Stopping LightDM')
            r = go('sudo service lightdm stop')
            self.log.debug(r[1])
        return val          

    excl_conf = '--exclude "sessile_betas.h5" --exclude "*/data/*" --exclude "*/backups/*" --exclude "*/packages/*" --exclude "*/exeBackups/*"'
    """Exclude files from configuration backup."""

    # excl_exe='--exclude "*.py"'
    excl_exe = '--exclude "*.h5" --exclude "*/tests/storage/*" --exclude "*/.svn/*"'
    """Exclude files from exe backups"""

    def do_backup(self, source, odir, excl='', outfile=False):
        """Generalized backup."""
        if not os.path.exists(odir):
            os.makedirs(odir)
        # TODO: migrate to tarfile implementation providing progress updates
        if not outfile:
            outfile = datetime.datetime.now().strftime("%Y_%m_%d_%H-%M-%S")
        outfile = os.path.join(odir, outfile)
        n = 1
        outfile1 = outfile
        while os.path.exists(outfile1 + '.tar.bz2'):
            outfile1 = '{}_{}'.format(outfile, n)
            n += 1
        cmd = 'tar {} -cvhf {}.tar.bz2 -C "{}" .'.format(
            excl, outfile1, source, source)
        self.log.info('Starting backup:', cmd)
        r = go(cmd)
        msg = r[1]
        if len(msg) > tar_log_limit:
            self.log.debug('Truncating backup output', len(msg))
            msg = msg[:tar_log_limit] + '\n...[truncated]...'
        self.log.info('New backup finished:', r[0], msg)
        return msg

    def do_restore(self, source, dest):
        """Generalized restore."""
        if not os.path.exists(source):
            self.log.error('Selected backup file does not exist:', source)
            return 'Selected backup does not exist: ' + source
        # As config is stored with absolute paths, a simple untar should
        # restore everything
        cmd = 'tar -C "{}" -xvf "{}"'.format(dest, source)
        self.log.info('Restoring backup:', cmd)
        r = go(cmd)
        msg = r[1]
        if len(msg) > tar_log_limit:
            self.log.debug('Truncating restore output', len(msg))
            msg = msg[:tar_log_limit] + '\n...[truncated]...'
        self.log.info(
            'Restored backup {} to {} [exit:{}]:'.format(source, dest, r[0]), msg)
        return msg

    def get_doBackup(self):
        """Perform configuration backup."""
        odir = self.desc.getConf_dir() + 'backups/'
        return self.do_backup(params.confdir, odir, self.excl_conf)

    def get_doRestore(self):
        """Perform configuration restore"""
        source = self.desc.getConf_dir() + 'backups/' + self['backups']
        return self.do_restore(source, params.confdir)

    def get_doExeBackup(self):
        """Perform configuration backup."""
        odir = self.desc.getConf_dir() + 'exeBackups/'
        return self.do_backup(self.project_root(), odir, self.excl_exe)

    def get_doExeRestore(self):
        """Perform configuration restore"""
        source = self.desc.getConf_dir() + 'exeBackups/' + self['exeBackups']
        return self.do_restore(source, self.project_root())

    def get_applyExe(self):
        """Apply software version."""
        source = self.desc.getConf_dir() + 'packages/' + self['packages']
        if not os.path.exists(source):
            msg = 'Software version does not exist: impossible to apply.', source
            self.log.error(msg)
            return msg
        # Prepare number of steps
        self.setattr('upgradeProgress', 'max', 4)
        # Tell the main server which operation is in progress
        self.root.set('progress', self['fullpath'] + 'upgradeProgress')
        self['upgradeProgress'] = 1
        # First do a software backup:
        self.get_doExeBackup()
        self['upgradeProgress'] = 2
        # Then do a configuration backup:
        self.get_doBackup()
        self['upgradeProgress'] = 3
        # Clean the project root
        r = go('find "{0}" -name "*.pyc" -delete ; mkdir -pv {0}'.format(self.project_root()))
        self.log.debug('Cleaned current version', r[1])
        # Lastly, restore to the selected exe version
        r = self.do_restore(source, self.project_root())
        self['upgradeProgress'] = 0
        self.log.critical(
            'Upgrade to {} finished. Please restart Misura.'.format(self['packages']))
        return r

    def get_version(self):
        """Get current misura version"""
        return __version__

    def get_libs(self):
        """Get information about loaded libraries"""
        return get_lib_info()

    def get_env(self):
        """Get environment variables"""
        r = go('env')
        return r[1]

    def get_network(self):
        """Apply network configuration"""
        # Open /etc/network/interfaces and write current config
        return 'NotImplemented'

    def get_reboot(self):
        r = go('sudo reboot')
        self.log.warning('Reboot requested. Result:', r)
        return r

    def get_halt(self):
        r = go('sudo halt -p')
        self.log.warning('Shutdown requested. Result:', r)
        return r

    def project_root(self):
        return "/".join(params.mdir.split("/")[:-4])
