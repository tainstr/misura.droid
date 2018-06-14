# -*- coding: utf-8 -*-
"""
General Instrument class
"""
import os
from copy import deepcopy
import multiprocessing
from time import sleep
from datetime import datetime
from traceback import format_exc
import functools

from misura.canon.csutil import utime, initializeme, sharedProcessResources
from misura.droid import parameters as params
from .. version import __version__
from misura.droid import share
from misura.droid import device
from measure import Measure
from sample import Sample
from cPickle import dumps

from twisted.internet import reactor, task

def isRunning(func):
    """Is running? decorator. Immediately return False if test is no longer running, or true if this is a device."""
    @functools.wraps(func)
    def isRunning_wrapper(self, *a, **k):
        # Subordered to another instrument
        if self.isDevice:
            return True
        # Unit test
        if not self.root:
            return True
        if self.root.get('isRunning') and self.desc.get('running') == 1 and not self['closingTest']:
            return func(self, *a, **k)
        return False
    return isRunning_wrapper


class Instrument(device.Measurer, device.Device):

    """Definition of a generic measurement instrument."""
    enabled = True
    measure_cls = Measure
    sample_cls = Sample
    outFile = False
    acquisition_devices = []
    mapped_devices = []
    camera_roles = []
    devicenames = []
    presets = {}
    initializing = True
    isDevice = False
    conf_def = deepcopy(device.Device.conf_def + device.Measurer.conf_def)
    conf_def += [{"handle": 'mapRoleDev', "name": 'Map To Dev',
                  "current": 'Map To Dev', "type": 'Button', "readLevel": 3},
                 {"handle": 'devices', "name": 'Acquisition Devices List',
                  "current": [], "attr": ['Hidden'], "type": 'List'},
                 {"handle": 'initTest', "name": 'Initializing New Test',
                     "type": 'Progress', "attr": ['Runtime']},
                 {"handle": 'initInstrument', "name": 'Initializing instrument',
                     "type": 'Progress', "attr": ['Runtime']},
                 {"handle": 'closingTest', "name": 'Closing the current test',
                     "type": 'Progress', "attr": ['Runtime']},
                 {"handle": 'out_tot', "name": 'Monitored datasets',
                     "type": 'Integer', "attr": ['ReadOnly']},
                 {"handle": 'out_up', "name": 'Updated datasets',
                     "type": 'Integer', "attr": ['ReadOnly', 'History']},
                 ]

    def __init__(self, parent=None, node=False):
        if not node:
            node=self.__class__.__name__
        if parent:
            opt = 'eq_' + node
            if parent.has_key(opt):
                if not parent[opt]:
                    self.enabled = False
                    print 'Instrument is disabled:', node
                    return

        self.name = node
        device.Device.__init__(self, parent=parent, node=node)
        self['initializing'] = True
        self.log.debug('DONE DEVICE INIT', node)
        self.name = node
        self.naturalName = node
        self.desc.setConf_dir(self.main_confdir + self.name + '/')
        self.kiln = False
        if node != 'kiln' and self.root is not None:
            self.kiln = getattr(self.root, 'kiln', False)
        self.samples = []
        self.outFile = False
        self.log.debug('PRE DEVICES', self.devices)
        self.measure_cls(self, 'measure')
        self.log.debug('POST DEVICES', self.devices)
        # Il metodo set_nSamples di measure deve richiamare set_nSamples di
        self.measure.set_nSamples = self.set_nSamples
        self.summarized = 0
        self['name'] = self.name
        if hasattr(parent, 'instruments'):
            parent.instruments.append(self)
        self.distribute_scripts()

        if self.__class__.__name__ == 'Instrument':
            self.post_init()
        self.log.debug('DONE INSTRUMENT INIT', node)

    def post_init(self):
        print 'CALLING post_init'
        self['initializing'] = False
        self['zerotime'] = 0
        self.mapRoleDev()

    def set_name(self, foo):
        """The name option cannot be changed for an instrument object"""
        self.desc.set('name', self.name)
        return self.name

    def get_name(self):
        """The name option is its own self.name attribute"""
        return self.name

    def searchPath(self, devpath, devlist=False):
        if not devlist:
            devlist = self.samples + [self.measure]
        print 'Instrument.searchPath in', devlist
        return device.Device.searchPath(self, devpath, devlist)

    def buildSample(self, n):
        """Creates the `n`-th Sample object"""
        print 'CREATING SAMPLE %i for CLASS %r' % (n, self.sample_cls)
        node = 'sample%i' % n
        smp = self.sample_cls(parent=self, node=node)
        smp['name'] = 'Sample n. %i' % n
        smp.env.hdf = self.outFile
        return smp

    @initializeme(repeatable=True)
    def set_nSamples(self, n):
        """Define Sample objects which will contain informations about each sample during analysis"""
        # Create Role options
        if n < 1:
            n = 1
        if n > 16:
            n = 16
        n = device.Measurer.set_nSamples(self, n)
        # Creates all required samples
        self.log.debug('Instrument.set_nSamples', n)
        self.samples = []  # Clear samples list

        for i in range(n):
            name = 'sample%i' % i
            sample = getattr(self, name, False)
            # If the attr is missing, create the sample
            if not sample:
                sample = self.buildSample(i)
            else:
                self.log.debug('not building, found sample', i)
            # Append to the list of defined samples
            self.samples.append(sample)
            # Add sub samples
            self.samples += sample.samples
            # Set the output sample option path and roledev mapping
            opt = 'smp%i' % i
            self[opt] = [sample['fullpath'], 'default']
            self.roledev[opt] = (sample, 'default', False)
        # Remove unnecessary samples
        self.delete_samples_from(n)
        self.measure.desc.set('nSamples', n)
        # If the call is routed from the measure object, must directly set to
        # memory
        self.desc.set('nSamples', n)
        self._rmodel = False
        self.log.info('Compiling scripts')
        self.distribute_scripts()
        self.log.debug('Instrument.set_nSamples done', n)
        return n

    def delete_samples_from(self, start_sample):
        for i in range(start_sample, 16):
            name = 'sample%i' % i
            smp = getattr(self, name, False)
            if not smp:
                self.log.debug('No sample object nr.%i' % i)
                break
            self.log.debug('Closing sample object nr.%i' % i)
            #task.deferLater(reactor, 10, smp.close)
            smp.close()
            del smp
            self.subHandlers.pop(name, False)

    def get_Samples(self):
        return self.measure['nSamples']

    def assign_sample(self, smp, dev, i):
        """Assign sample `smp` to device `dev` at index `i`"""
        # Update number of samples on device
        if dev['nSamples'] < i:
            dev['nSamples'] = i
        opt = 'smp%i' % i
        if not dev.has_key(opt):
            self.log.error('No sample role defined {}'.format(i))
            return False
        val = dev[opt]
        val[0] = smp['fullpath']
        dev[opt] = val
        smp['ii'] = i
        return True

    def assign_samples(self, samples, devices):
        """Equally distribute `samples` into `devices`"""
        d = len(devices)
        if d == 0:
            self.log.error('No devices defined!')
            return False
        n = len(samples)
        if n == 0:
            self.log.error('No samples defined!')
            return False
        print samples, devices
        eq = n // d  # minimum samples per device
        rem = n % d
        for i in range(d):
            # will get an extra sample if index is smaller than remainder
            ni = eq + (i < rem)
            print 'Updating device nSamples to', ni
            devices[i]['nSamples'] = ni
        i = 0
        while i < n:
            di = i % d  # destination device
            ii = i // d     # sample index on device
            print 'assigning', i, di, ii
            dev = devices[di]
            if ii + 1 > dev['nSamples']:
                print 'Updating device nSamples to', ii + 1
                dev['nSamples'] = ii + 1
            self.assign_sample(samples[i], devices[di], ii)
            i += 1
        return True

    def get_mapRoleDev(self):
        return self.mapRoleDev()

    def mapRoleDev(self):
        """Retrieve configured roles and make their objects available as local attributes"""
        print 'mapRoleDev init'
        if self['initializing'] and not self['initInstrument']:
            self.log.error(
                'mapRoleDev: Cannot map devices to roles while still initializing!')
            return False
        if self.root_isRunning or self['closingTest']:
            self.log.error(
                'Device mapping is not allowed while acquisition is running. Aborted.')
            return False

        self['initializing'] = True
        desc = self.desc.describe()
        print 'mapRoleDev', desc['name']['current']
        self.devicenames = []
        self.presets = {}
        self.acquisition_devices = []
        self.mapped_devices = []
        self.camera_roles = []
        for handle, prop in desc.iteritems():
            r = self.map_role_dev(handle)
            if not r:
                continue
            obj, preset, io = r
            mro = obj['mro']
            if 'Camera' in mro:
                self.acquisition_devices.append(obj)
                self.camera_roles.append(handle)

            elif 'Balance' in mro:
                self.acquisition_devices.append(obj)

            # Publish the simple IO object (retrievable with get() call)
            if io is True:
                role = 'io_' + handle
                self.putSubHandler(role, io)
            # Add the object to devices list to be published via xmlrpc
            # Avoid accounting two times the same object
            elif obj.naturalName not in self.devicenames:
                name = obj.naturalName
                if obj.has_key('devpath'):
                    name = obj['devpath']
                self.mapped_devices.append(obj)
                self.devicenames.append(name)
                self.presets[obj['devpath']] = preset
            else:
                print 'OBJECT ALREADY IN DEVICES', handle, obj

        #############################################
        # Setting current acquisition roles on each device
        for dev in self.devices + self.mapped_devices:
            if getattr(dev, 'name', False) == 'kiln':
                continue
            role = self.dev2role(dev['fullpath'])
            if not role:
                continue
#           print 'putsubhandler ', dev,role
            self.putSubHandler(role, dev)
        # Special kiln configurations
        if self.name != 'kiln' and self.kiln:
            self.kiln.mapRoleDev()
        elif self.name == 'kiln':  # ??? really needed ???
            self.kiln = self
        if self.kiln is not False and self.kiln != self:
            self.kiln.isDevice = True
            self.mapped_devices.append(self.kiln)
            self.acquisition_devices.append(self.kiln)

        self.manage_thermal_cycle_motor_options()
        # Reset initializing flag only if not during a larger instrument initialization
        if not self['initInstrument']:
            self['initializing'] = False
        self.log.debug('DONE MAPROLEDEV', self.acquisition_devices, repr(self.kiln), self['name'])
        return True

    def manage_thermal_cycle_motor_options(self):
        should_show = bool(self.kiln and self.kiln.motor)

        hide_or_show = {
            False: self.hide_measure_option, True: self.show_measure_option}

        for option in ['kilnBeforeStart', 'kilnAfterEnd']:
            hide_or_show[should_show](option)

    def hide_measure_option(self, option_name):
        attr = self.measure.gete(option_name)['attr']
        if 'Hidden' in attr:
            return

        attr.append('Hidden')
        self.measure.setattr(option_name, 'attr', attr)

    def show_measure_option(self, option_name):
        attr = self.measure.gete(option_name)['attr']
        if not 'Hidden' in attr:
            return

        attr.remove('Hidden')
        self.measure.setattr(option_name, 'attr', attr)

    def start_acquisition(self, writeLevel=1, userName='unknown'):
        if writeLevel < 1:
            self.log.critical('Not authorized request: start_acquisition')
            return 'NOT AUTHORIZED'
        self.measure['operator'] = userName
        r = self._start_acquisition()
        self.log.info(r)
        return r
    xmlrpc_start_acquisition = start_acquisition

    def end_status(self, msg, *args):
        """Autolog and concatenate endStatus messages"""
        if len(args):
            msg = msg.format(*args)
        if self.measure['endStatus']:
            msg = self.measure['endStatus'] + '\n' + msg
        self.measure['endStatus'] = msg
        self.log.critical('End status: ', msg)
        return msg

    def clear_endStatus_messages(self):
        """Cancel all endStatus messages"""
        self.measure['endStatus'] = ''
        if self.root:
            self.root['endStatus'] = ''
        k = self.kiln if self.kiln else self
        k.measure['endStatus'] = ''

    def _start_acquisition(self):
        if self.root.get('isRunning') or self['initTest']:
            self.log.debug('Already running')
            return 'Already running'
        if self['closingTest']:
            self.log.debug('Closing previous test')
            return 'Closing previous test'
        # Prepare number of steps
        self.setattr('initTest', 'max', len(self.acquisition_devices) + 4 + 6)
        # Init the counter to 1
        self['initTest'] = 1
        self.clear_endStatus_messages()
        # Tell the main server which operation is in progress
        self.root.set('progress', self['fullpath'] + 'initTest')
        # Sync kiln position before anything else
        # TODO: ignore if TC starts with an event!!!
        k = self.kiln if self.kiln else self
        if not k is self:
            k['running'] = False
            
        if k.has_key('powerSwitch') and not k['powerSwitch']:
            self['initTest'] = 0
            msg = k.powerSwitch_message() + '\n Cannot start a new test!'
            self.log.error(msg)
            return msg
        
        kae = self.measure['kilnBeforeStart']
        # not undefined and no closing movement in the thermal cycle and kiln
        # is real kiln (for UT)
        if kae != -1 and hasattr(k, 'set_motorStatus'):
            self.log.info('Moving the furnace at the start of the test', kae)
            k.set_motorStatus(kae, block=True)
            self['initTest'] = 2
        self.isDevice = False
        ini_acq = self.init_acquisition()
        self['initTest'] = 3
        if not ini_acq:
            self['initTest'] = 0
            self.log.error('Impossible to init acquisition')
            return 'Impossible to init acquisition'
        for dev in self.acquisition_devices:
            self['initTest'] += 1
            if dev is False:
                continue
            dev.isDevice = True
            if dev == self:
                dev.isDevice = False
            # FIXME: maybe set_running should be moved to supervisor.
            dev.set_running(True, self['zerotime'])
        self.log.info('Compiling scripts')
        self.distribute_scripts()
        self.log.debug('Starting supervisor process...')
        self.process = multiprocessing.Process(target=self.supervisor,
                                               kwargs={'spr':sharedProcessResources})
        self.process.daemon = self._daemon_acquisition_process
        self.desc.set('running', 1)
        self.process.start()
        self['pid'] = self.process.ident
        self['initTest'] = 0
        self.log.debug(
            'Started supervisor process with pid', self.process.ident)
        return 'Acquisition started'

    def stop_acquisition(self, save=True, writeLevel=1,  userName='unknown'):
        if writeLevel < 1:
            self.log.critical('Not authorized request: stop_acquisition')
            return 'NotAuthorized'
        if not self.root['isRunning']:
            self.log.info('Acquisition already stopped. Nothing to do.')
            return False
        self.end_status('Operator [{}] requested the test to stop.', userName)
        return self._stop_acquisition(save)
    xmlrpc_stop_acquisition = stop_acquisition

    process = False

    def _stop_acquisition(self, save=True, auto=False):
        """Stops the acquisition cycle and closes the output file.
        If save=False, the output file is then deleted
        If auto=True, supervisor is the caller and should not be killed."""
        elapsed = self.measure['elapsed']
        self.log.debug('_stop_acquisition', save, auto, elapsed)
        self['initTest'] = 0
        # Prepare number of steps
        self.setattr(
            'closingTest', 'max', 4 + 2 * len(self.acquisition_devices))
        self['closingTest'] = 1
        # Tell the main server which operation is in progress
        self.root.set('progress', self['fullpath'] + 'closingTest')
        self.root.set('isRunning', False)
        if self.kiln:
            self.kiln['P'] = 0.
        if self.kiln and self.kiln is not self:
            self.kiln['analysis'] = False
            kend = self.kiln.measure['endStatus']
            if kend:
                self.end_status(
                    'Stop requested by thermal control. Reason: {}', kend)
        if self.root['endStatus']:
            self.end_status(
                '####\nGeneral stop requested:\n{}\n####', self.root['endStatus'])

        # Deactivate running flags (signal stop)
        for dev in self.acquisition_devices:
            self['closingTest'] += 1
            if dev is False:
                continue
            dev.log.info('Stopping acquisition requested by instrument')
            dev.desc.set('analysis', False)
            dev.desc.set('running', 0)
        sleep(.5)

        self.log.debug('Stop signalled. Joining child processes')
        # Forcefully stop
        for dev in self.acquisition_devices:
            self['closingTest'] += 1
            if dev is False:
                continue
            # This will force joining
            self.log.debug('Joining:', dev['fullpath'])
            dev['running'] = 0

        # Supervisor
        if not auto:
            self.log.debug('Stopping supervisor process')
            self['running'] = 0
            self.log.debug('Stopped supervisor process')
            self.process = False
            self['closingTest'] += 1

        # Close storage
        self.log.debug('Closing output file')
        if save:
            try:
                self.close_storage(elapsed)
            except:
                self.log.critical('Instrument._stop_acquisition', format_exc())
        else:
            self.outFile.close()
        self.root.storage['live'] = ''  # deregister
        f = self.measure.get('measureFile')
        if os.path.exists(f) and (not save):
            self.measure['uid'] = ''
            sleep(2)
            self.log.info('Removing output file.', f)
            os.remove(f)

        self['closingTest'] += 1

        k = self.kiln if self.kiln else self
        kae = self.measure['kilnAfterEnd']
        if kae != -1 and hasattr(k, 'set_motorStatus'):
            self.log.debug('Opening furnace after acquisition')
            k.set_motorStatus(kae, block=False)
            self['closingTest'] += 1
        for dev in self.acquisition_devices:
            dev['zerotime'] = -1
        self.root.set('zerotime', 0.)
        self['zerotime'] = 0.
        self.post_stop_acquisition()
        self.root.set('runningInstrument', 'None')
        self['closingTest'] = 0
        self.log.debug('acquisition stopped')
        # Force restart with current instrument]
        self.root['restartOnNextCheck'] = True
        return 'acquisition stopped'

    def post_stop_acquisition(self, *args):
        """This can be implemented by children to process eventual cleanup."""
        pass

    def init_acquisition(self):
        """Prepares the instrument and its devices to start the acquisition processes"""
        if self.kiln:
            self.kiln['cooling'] = False
        self.reset_acquisition()
        self.measure.reset_acquisition()
        for i in range(self.measure['nSamples']):
            smp = getattr(self, 'sample%i' % i)
            smp.reset_acquisition()
        # Update `devices` attribute (and also mapRoleDev)
        self.get_devices()
        # init current devices
        for dev in self.devices + self.mapped_devices:
            self.log.info('init:', dev.naturalName)
            # Init dev acquisition. Except for the kiln special "device".
            if dev is self.kiln:
                continue
            else:
                dev.init_acquisition(instrument=self.name)
                if dev.has_key('analysis'):
                    dev['analysis'] = True
        self.sit = 0  # supervisor iteration
        self.isRunning = True  # local acquisition status
        self.wait = 0  # autotuning sleep
        self.krect = 0
        self['zerotime'] = utime()
        self.measure['zerotime'] = self['zerotime']
        self.root.set('zerotime', self['zerotime'])
        self.measure['elapsed']  # triggers an 'elapsed' opt update
        self.measure.desc.set(
            'date', datetime.now().strftime("%H:%M:%S, %d/%m/%Y"))
        self.log.debug('init_acquisition isDevice', self.isDevice)
        if not self.isDevice:
            self.root['isRunning'] = True
            self.root['runningInstrument'] = self.name
            self.init_storage()
        return True

    def get_initializing(self):
        """The initializing state is set whenever:
        - object is initializing
        - instrument configuration is being loaded ('initInstrument')
        - a new test is being started or stopped"""
        return self.desc.get('initializing') or self['initInstrument'] or self['initTest'] or self['closingTest']

    def deinit(self, nval):
        if nval == 0:
            self.desc.set('initializing', False)
        return nval

    set_initInstrument = deinit
    set_initTest = deinit
    set_closingTest = deinit

    def set_default_preset(self):
        is_preset_set = self.set_preset('default')
        if not is_preset_set:
            is_preset_set = self.set_preset('factory_default')
        return is_preset_set

    def init_instrument(self, soft=False, preset=False):
        """This function is called client-side when the user enters an Instrument.
        Default configurations are loaded into the devices (eg, motors go to their initial position)"""
        if self.root.get('isRunning') + self['initializing']:
            self.log.error(
                'Other operation in progress: cannot init instrument')
            return False
        self.clear_endStatus_messages()
        self.log.info(
            'Initializing instrument', self.name, 'with preset', preset)
        self.root.set('lastInstrument', self.name)
        # Prepare number of steps
        self.log.info('Checking preset')
        nSamples = self['nSamples']
        if not (preset and self.set_preset(preset)):
            self.set_default_preset()
        self.log.info('Assigning samples')
        self.setattr('initInstrument', 'max', len(self.root.deviceservers) + 3)
        self['initInstrument'] = 1
        self['zerotime'] = 0
        self['nSamples'] = nSamples

        # Tell the main server which operation is in progress
        self.root.set('progress', self['fullpath'] + 'initInstrument')
        self.mapRoleDev()
        self['initInstrument'] = 2
        ret = True
        # Init instrument on *all* physical devices
        for ds in self.root.deviceservers:
            dsname = ds['name']
            self.log.info('Initializing devices:', dsname)
            try:
                ds.init_instrument(preset or self.name)
            except:
                self.log.error(
                    'Cannot initialize devices', dsname, '\n',  format_exc())
                ret = False
                break
            self['initInstrument'] += 1
        self['initInstrument'] = 0
        self['initializing'] = 0
        if ret:
            for instrument in self.root.instruments:
                if instrument is not self and instrument['name'] != 'kiln':
                    instrument.delete_samples_from(0)
        return ret

    def xmlrpc_init_instrument(self, *args, **kwargs):
        self.init_instrument(*args, **kwargs)

    def save_conf(self, tree, elapsed=-1):
        """Save a pickled object configuration into a file"""
        where = '/conf'
        if elapsed < 0:
            elapsed = self.measure['elapsed']
        self.log.info('Test duration was: elapsed, ', elapsed)
        tree[self.name]['measure']['self']['elapsed']['current'] = elapsed
        tree['self']['runningInstrument']['current'] = self.name
        self.outFile.filenode_write(where, obj=tree)
        self.log.debug('dumped pickle ok')
        attrs = {'misura': __version__,  # misura version
                 'versions': 0,  # available data revisions
                 'instrument': self.name,
                 'date': self.measure['date'],
                 'serial': self.root.get('eq_sn'),
                 'uid': self.measure['uid'],
                 'elapsed': elapsed,
                 'zerotime': self['zerotime']}
        self.outFile.set_attributes('/', name='conf', attrs=attrs.copy())
        return True

    @property
    def caldir(self):
        # return self.desc.getConf_dir()+'/calibration/'
        return params.datadir + self.name + '/calibration/'

    def init_storage(self):
        """Initializing the output HDF5 file for writing."""
        self.summarized = 0
        # Try to close the output file if defined
        if getattr(self, 'outFile', False):
            try:
                self.log.debug(
                    'Closing previous outFile', self.outFile.get_path())
                self.outFile.close()
            except:
                pass
            del self.outFile

        # Output file
        forcepath = False
        if self.measure['flavour'] == 'Calibration':
            forcepath = self.caldir
        self.log.debug('Creating self.outFile')
        # Notice: this is a managed OutputFile object which can be shared
        # between processes.
        self.outFile = self.root.storage.new(self.name, shortname=self.measure.desc.get('name'),
                                             forcepath=forcepath, title='Acquisition test',
                                             shm_path=share.dbpath, zerotime=self['zerotime'])
        self.log.debug('Done creating self.outFile')
        mf = self.outFile.get_path()
        uid = self.outFile.get_uid()
        self.measure.desc.set('id', self.outFile.get_id())
        self.measure.desc.set('uid', uid)
        self.measure.desc.set('measureFile', mf)
        self.log.debug('New test file has been created:',  mf, id, uid)
        self.lastLogTime = utime()
        # Save entire configuration tree
        tree, msg = self.root.tree()
        self.log.debug('Saving configuration tree:\n', msg)
        if not self.save_conf(tree):
            return False
        self.outFile.flush()
        self.root.storage['live'] = uid
        return True

    def close_storage(self, elapsed=-1):
        """Saves final configuration and closes outFile.
        """
        if self.outFile is False:
            self.log.critical(
                'Impossible to close storage: no output file defined.')
            return False
        # Save updated metadata and elapsed time
        self.save_metadata(elapsed)
        self.outFile._timeout = 600
        try:
            self.outFile.sync(only_logs=True)
        except:
            self.log.critical(format_exc())
        # Wait for logs to be collected
        sleep(1)
        try:
            # Stop collection and commit latest changes
            self.outFile.stop()
            sleep(1)
        except:
            self.log.critical(format_exc())
        s = self.outFile.sign()
        self.log.debug('Test File signed:', s)
        self.log.debug('Storage closed.')
        r = self.root.storage.appendFile(self.measure['measureFile'])
        self.outFile.close()
        self.root.storage['live'] = ''  # deregister
        # Stop the outFile ProcessProxy
        self.outFile._stop()
        self.outFile = False
        if not r:
            self.log.error('Error appending test file to database.',
                           self.measure['measureFile'],
                           self.measure['id'])
            return False
        self.log.debug('File appended to database:',
                       self.measure['measureFile'],
                       self.measure['id'])
        return True

    def save_metadata(self, elapsed=-1):
        """Last characterization and save configuration."""
        self.characterization()
        self.characterization(period='end')
        # Save again configuration tree, with updated metadata
        tree, msg = self.root.tree()
        self.log.debug('Saving configuration tree:\n', msg)
        self.save_conf(tree, elapsed)
        self.outFile.flush()

    def prepare_control_loop(self, zt=-1):
        self.sit = 0
        self.wait = 0
        if zt > 0:
            self['zerotime'] = zt
        self['analysis'] = True
        self.log.info('Control loop prepared.')
        sleep(.5)
        return True

    def supervisor(self, spr=False):
        """Acquisition process for data collection and output file writing"""
        if spr: spr()
        self.log.info('Preparing supervisor', self.root.get(
            'isRunning'), self.isRunning, self.measure['measureFile'])
        if not self.prepare_control_loop():
            self.log.error(
                'Not starting supervisor: prepare_control_loop failed')
            self.desc.set('running', 0)
            self.root.set('isRunning', False)
            return
        self.log.info(
            'Supervisor cycle START', self.root.get('isRunning'), self.isRunning)
        # Infinite call to control_loop(), until True
        loop = True
        while loop:
            try:
                loop = self.control_loop()
            except:
                self.log.error('Supervisor error:', format_exc())
                break
            
        if self['closingTest']:
            # the acquisition was stopped as a consequence of calling _stop_acquisition(),
            # which  already set the closingTest flag
            self.end_status('Acquisition was interrupted')
        else:
            # the acquisition spontaneously ended: closing operations still
            # pending.
            self.end_status('Acquisition ended')
            self._stop_acquisition(save=True, auto=True)
        self.desc.set('running', 0)
        self['analysis'] = False
        # Join any unfinished child proc
        multiprocessing.active_children()

    def check(self):
        """Completely override Device.check(). Do not want child devices to be checked."""
        if self['initializing']:
            return True
        # Join any unfinished child proc
        multiprocessing.active_children()
        # Check for spontaneous acquisition end
        if self['running'] + self['initTest'] + self['closingTest'] == 0:
            if self.outFile is not False:
                self.log.warning('Dereferencing output file')
                self.outFile = False
                return False
        return True

    @isRunning
    def summary(self, t, interval=1):
        """Periodic actions during the test"""
        if self['initTest']:
            if t > 6:
                self['initTest'] = False
            else:
                self['initTest'] += 1
        # Continuous characterization
        cal = self.measure['flavour'] == 'Calibration'
        if not cal and t > 60:
            self.characterization(period='always')
        # Periodic characterization
        if t > 60 and t % 16 == 0 and not cal:  # caratterizzazione ogni 16 sec
            self.characterization()
        self.post_summary()
        return self.check_termination()

    def check_termination(self):
        """Check termination conditions."""
        # Device error counting
        ret = True
        err = False
        for obj in self.mapped_devices:
            if obj['anerr'] > 0:
                err = True
                break
        if err:
            self['anerr'] += 1
        else:
            self['anerr'] = 0

        if self['anerr'] > self.measure['errors']:
            self.end_status(
                'Maximum consecutive analysis errors limit reached. Stopping now.')
            ret = False

        dur = self.measure['duration']
        if dur > 0:
            if self.measure['elapsed'] > dur * 60:
                self.end_status('Maximum test duration reached. Stopping now.')
                ret = False
        return ret

    def post_summary(self):
        """Placeholder for standard and derived values calculation."""
        pass

    @isRunning
    def control_loop(self, t=None, step=2., sleeping=True):
        """Common iteration for any supervisor loop"""
        if self.outFile is False:
            self.log.error('No output file defined!')
            return False
        try:
            N, sc = self.outFile.sync()
        except RuntimeError:
            mf = self.measure['measureFile']
            self.end_status(
                'Connection to output file was lost!', mf)
            return False
        self['out_tot'] = N
        self['out_up'] = sc
        # Update elapsed time
        d = self.measure['elapsed']
        # TODO: update other metadata?
        # run self.summary each `step` seconds
        if step == 0:  # if step=0, always do summary()
            d2 = t
        if step > 0:
            d2 = d // step
            t = step * (d2 - 1)
        ret = True
        if d2 > self.summarized or not sleeping:
            self.summarized = d2
            ret = self.summary(t)
        # Supervisione non-totalizzante (sleeping)
        if not sleeping:
            return ret
        self.sit += 1
        # 1. Quantizzo le chiamate a status: 1 ogni 10 iterazioni
        if self.sit % 10 == 0:
            self.isRunning = self.root.get('isRunning')
            self.sit = 1
        sleep(0.01)
        return ret

    def get_devices(self):
        """Returns a list of acquisition devices and their role"""
        if not self.root['isRunning']:
            self.mapRoleDev()
        r = []
        for d in set(self.devices + self.mapped_devices):
            fp = d['fullpath']
            role = self.dev2role(fp)
            if not role:
                if fp == '/kiln/':
                    role = 'kiln'
                elif fp.endswith('/measure/'):
                    role = 'measure'
                else:
                    role = 'NoRole'
            r.append((role, fp))
        self['devices'] = r
        return r

    def reset_regions(self):
        cameras = {key: cam for key, cam in self.roledev.iteritems() if key.startswith(
            "camera") and cam[0]}

        for camera in cameras.values():
            camera[0].init_samples()
