#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
import os
from copy import deepcopy
import datetime
from time import time
from commands import getstatusoutput as go
from . import parameters as params
import device
from misura.droid.version import __version__


def get_lib_info():
    """Find all libraries loaded in current process and their real shared object name with version"""
    if params.isWindows:
        return 'Unsupported on Windows platforms'
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

def parse_vmstat():
    if params.isWindows:
        return {}
    vm = {}
    r = go('vmstat -s -S M')[1]
    r=r.replace('  ','').replace('  ','').replace('\n ','\n')
    if r[0]==' ': r = r[1:]
    for line in r.splitlines():
        line = line.split(' ')
        val = int(line.pop(0))
        key = ' '.join(line)
        vm[key] = val
    return vm

tar_log_limit = 1e6

def get_today_string():
    return datetime.datetime.now().strftime("%Y_%m_%d_%H-%M-%S")

class Support(device.Device):

    """Support functionalities. Backup/restore, upgrade, remote assistance."""
    naturalName = 'support'
    conf_def = deepcopy(device.Device.conf_def)
    conf_def += [
        # Conf Backups
        {"handle": 'stopUI', "name": 'Stop embedded UI', "current": False, "type": 'Boolean',"writeLevel":5},
        {"handle": u'logs', "name": u'Log archive',
            "type": 'FileList', 'attr': ['Runtime']},
        {"handle": u'doLogs', "name": u'Refresh log archive',
            "type": 'Button', "parent": 'logs'},
        {"handle": u'backups', "name": u'Available backups',
            "type": 'FileList', 'attr': ['Runtime']},
        {"handle": u'doBackup', "name": u'New configuration backup',
            "type": 'Button', "parent": 'backups'},
        {"handle": u'doRestore', "name": u'Restore configuration backup',
            "type": 'Button', "parent": 'backups'},
        {"handle": u'backupPackage', "name": u'Last applied backup name',
            "type": 'String', 'attr': ['ReadOnly'], "parent":'backups'},
        {"handle": u'backupDate', "name": u'Last applied backup date',
            "type": 'String', 'attr': ['ReadOnly'], "parent":'backups'},
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
        {"handle": u'upgradeProgress', "name": u'Upgrade/restore progress',
            "type": 'Progress', "attr": ['Runtime']},
        # System info
        {"handle": u'version', "name": u'Misura version',
            "type": 'String', 'attr': ['ReadOnly']},
        {"handle": u'versionPackage', "name": u'Last applied package name',
            "type": 'String', 'attr': ['ReadOnly'], "parent":'version'},
        {"handle": u'versionDate', "name": u'Last applied package date',
            "type": 'String', 'attr': ['ReadOnly'], "parent":'version'},
        {"handle": u'versionString', "name": u'Extended version string',
            "type": 'TextArea', 'attr': ['ReadOnly'], "parent":'version'},
        {"handle": u'libs', "name": u'Loaded libraries info',
            "type": 'Button'},
        {"handle": u'env', "name": u'Environment variables', "type": 'Button'},
        {"handle": u'dmesg', "name": u'System logs', "type": 'TextArea'},

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
        
        {"handle": u'sys', "name": u'System Info', "type": 'Section'},
        {"handle": u'sys_usedRam', "name": u'Used RAM', "unit": "percent",
            "attr":['ReadOnly', 'History'], "type": 'Float'},
        {"handle": u'sys_ram', "name": u'Total RAM', "unit": "megabyte",
            "attr":['ReadOnly'], "type": 'Float'},
        {"handle": u'sys_usedSwap', "name": u'Used swap', "unit": "percent",
            "attr":['ReadOnly', 'History'], "type": 'Float'},
        {"handle": u'sys_swap', "name": u'Total swap', "unit": "megabyte",
            "attr":['ReadOnly'], "type": 'Float'},
        {"handle": u'sys_cpu', "name": u'CPU load', "unit": "percent",
            "attr":['ReadOnly', 'History'], "type": 'Float'},
        {"handle": u'sys_cpuTicks', "name": u'Active CPU ticks',
            "attr":['ReadOnly', 'Runtime'], "type": 'Float'},
        {"handle": u'sys_cpuTicksIdle', "name": u'Idle CPU ticks',
            "attr":['ReadOnly', 'Runtime'], "type": 'Float'},
        {"handle": u'sys_temp', "name": u'CPU Temperature', "unit": 'celsius',
            "attr":['ReadOnly', 'History'], "type": 'Float'},
        {"handle": u'sys_time', "name": u'Last system read', 
            "attr":['ReadOnly', 'Runtime'], "type": 'Time'},
        
    ]

    def __init__(self, parent=None, node='support'):
        device.Device.__init__(self, parent=parent, node=node)
        self.name = 'support'
        self['name'] = 'Support'
        self['comment'] = 'Support, upgrade, backup, restore, get assistance'
        self['devpath'] = 'support'
        self.post_connection()
        self.set_stopUI(self['stopUI'])
        self.vmstat()
        if os.path.exists(params.version_file):
            self['versionString'] = open(params.version_file, 'r').read()

            
    def set_stopUI(self, val):
        if val:
            self.log.debug('Stopping LightDM')
            r = go('sudo service lightdm stop')
            self.log.debug(r[1])
        return val          

    excl_conf = '--exclude "sessile_betas.h5" --exclude "*/data/*" --exclude "*/support/*/*" '
    """Exclude files from configuration backup."""

    # excl_exe='--exclude "*.py"'
    excl_exe = '--exclude "*.h5" --exclude "*/tests/storage/*" --exclude "*/.svn/*"'
    """Exclude files from exe backups"""

    def do_backup(self, source, odir, excl='', outfile=False, overwrite=False):
        """Generalized backup."""
        if params.isWindows:
            return 'unsupported', 'Unsupported'
        if not os.path.exists(odir):
            os.makedirs(odir)
        # TODO: migrate to tarfile implementation providing progress updates
        if not outfile:
            outfile = get_today_string()
        outfile = os.path.join(odir, outfile)
        n = 1
        outfile1 = outfile
        while os.path.exists(outfile1 + '.tar.bz2'):
            if overwrite:
                os.remove(outfile1+ '.tar.bz2')
                break
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
        self.log.info('New backup was successful. These files were archived:', r[0], msg)
        return outfile1+'.tar.bz2', msg

    def do_restore(self, source, dest):
        """Generalized restore. Returns status and message."""
        if params.isWindows:
            return False, 'Unsupported'
        if not os.path.exists(source):
            self.log.error('Selected backup file does not exist:', source)
            return False, 'Selected backup does not exist: ' + source
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
            'Successfully restored archive {} to {} [exit:{}]:'.format(source, dest, r[0]), msg)
        return True, msg
    
    def save_last_version_info(self, prefix, package_name):
        self[prefix+'Package'] = package_name
        self[prefix+'Date'] = get_today_string()
        self.save('default')     

    def get_doBackup(self):
        """Perform configuration backup."""
        odir = self.desc.getConf_dir() + 'backups/'
        outfile, msg = self.do_backup(params.confdir, odir, self.excl_conf)
        self['backups'] = os.path.basename(outfile)
        return msg
    
    def get_doLogs(self):
        """Perform logs backup."""
        odir = self.desc.getConf_dir() + 'logs/'
        outfile, msg = self.do_backup(params.confdir+'data/log/', odir, outfile='logs', overwrite=True)
        self['logs'] = os.path.basename(outfile)
        return msg

    def get_doRestore(self):
        """Perform configuration restore"""
        source = self.desc.getConf_dir() + 'backups/' + self['backups']
        status, msg = self.do_restore(source, params.confdir)
        if status:
            self.save_last_version_info('backup', 'backups://'+self['backups'])
        return msg

    def get_doExeBackup(self):
        """Perform configuration backup."""
        odir = self.desc.getConf_dir() + 'exeBackups/'
        outfile, msg = self.do_backup(self.project_root(), odir, self.excl_exe)
        self['exeBackups'] = os.path.basename(outfile)
        return msg

    def get_doExeRestore(self):
        """Perform configuration restore"""
        source = self.desc.getConf_dir() + 'exeBackups/' + self['exeBackups']
        status, msg = self.do_restore(source, self.project_root())
        if status:
            self.save_last_version_info('version', 'exeBackups://'+self['exeBackups'])
        return msg

    def get_applyExe(self):
        """Apply software version."""
        if params.isWindows:
            return 'Unsupported'
        source = self.desc.getConf_dir() + 'packages/' + self['packages']
        if not os.path.exists(source) or not self['packages']:
            msg = 'Software version does not exist: impossible to apply.', source
            self.log.error(msg)
            return msg
        if not source.endswith('.tar'):
            msg = 'Selected upgrade package is invalid. Removing.'
            self.log.error(msg)
            os.remove(source)
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
        
        status, r = self.do_restore(source, self.project_root())
        self['upgradeProgress'] = 0
        if status:
            msg = 'Upgrade to {} finished successfully. \nPlease restart Misura to apply it!\n'.format(self['packages'])
            self.save_last_version_info('version', 'packages://'+self['packages'])
        else:
            msg = 'Failed to upgrade to {}!\n'.format(self['packages'])
        self.log.critical(msg)
        return r+msg

    def get_version(self):
        """Get current misura version"""
        return __version__

    def get_libs(self):
        """Get information about loaded libraries"""
        return get_lib_info()

    def get_env(self):
        """Get environment variables"""
        if params.isWindows:
            return 'unsupported'
        r = go('env')
        return r[1]
    
    def get_dmesg(self):
        if os.name=='nt':
            return 'NotImplemented'
        s, out = go('dmesg')
        return out

    def get_network(self):
        """Apply network configuration"""
        # Open /etc/network/interfaces and write current config
        return 'NotImplemented'

    def get_reboot(self):
        if params.isWindows:
            return 'unsupported'
        r = go('sudo reboot')
        self.log.warning('Reboot requested. Result:', r)
        return r

    def get_halt(self):
        if params.isWindows:
            return 'unsupported'
        r = go('sudo halt -p')
        self.log.warning('Shutdown requested. Result:', r)
        return r

    def project_root(self):
        return params.sep.join(params.mdir.split(params.sep)[:-4])
    
    def vmstat(self):
        if params.isWindows:
            return {}
        vm=parse_vmstat()
        t=time()
        self['sys_ram'] = vm['M total memory']
        self['sys_swap'] = vm['M total swap']
        self['sys_usedRam'] = 100.*vm['M used memory']/vm['M total memory']
        if vm['M total swap']:
            self['sys_usedSwap'] = 100.*vm['M used swap']/vm['M total swap']
        cpu = [vm[k] for k in ['non-nice user cpu ticks',
                               'nice user cpu ticks',
                               'IO-wait cpu ticks',
                               'IRQ cpu ticks',
                               'softirq cpu ticks',
                               'stolen cpu ticks']]
        dt = t-self['sys_time']
        if dt<0:
            self['sys_time'] = t
            return vm
        
        cpu = sum(cpu)
        dcpu = cpu-self['sys_cpuTicks']
        didle = vm['idle cpu ticks']-self['sys_cpuTicksIdle']
        self['sys_cpu'] = 100.*dcpu/(dcpu+didle)
        self['sys_time'] = t
        self['sys_cpuTicks'] = cpu
        self['sys_cpuTicksIdle'] = vm['idle cpu ticks']
        return vm
        
    
    def get_sys_usedRam(self):
        self.vmstat()
        return self.desc['sys_usedRam']
    
    def get_sys_usedSwap(self):
        self.vmstat()
        return self.desc['sys_usedSwap']
    
    def get_sys_cpu(self):
        self.vmstat()
        return self.desc['sys_cpu']
    
    def get_sys_temp(self):
        """Returns the maximum temperature found in all thermal zones"""
        if params.isWindows:
            return 0
        st, msg = go('cat /sys/class/thermal/thermal_zone*/temp')
        if st!=0:
            return 0
        temps = map(float, msg.splitlines())
        return max(temps)/1000.0
    
    def check(self):
        self.vmstat()
        self['sys_temp'] = self.get_sys_temp()
        return super(Support, self).check()

    

