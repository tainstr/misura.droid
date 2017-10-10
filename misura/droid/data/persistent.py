# -*- coding: utf-8 -*-
"""Data management and formats"""
import os
from traceback import format_exc
from .. import parameters as params
from .. import utils
from misura.canon import option

def rename(new_name, old_name, overwrite,
           conf_obj, conf_dir, log, ext=params.conf_ext):
    if not new_name:
        return log.error('Rename: No new name defined'), False
    obj = conf_obj
    if old_name:
        obj = os.path.join(conf_dir, old_name + ext)
    if not os.path.exists(obj):
        return log.error('No source preset to be renamed:', obj, 
                              conf_obj, old_name), False
    
    new_obj = os.path.join(conf_dir, new_name + ext)
    if os.path.exists(new_obj) and not overwrite:
        return log.error('Cannot overwrite existing preset: ', new_name), False
    
    os.rename(obj, new_obj)
    return log.info('Configuration renamed:', new_name), True

# TODO: separe persistency functionality so that it can be easily changed
class PersistentConf(option.Conf):

    """Persistency through saving on CSV files on a structured filesystem."""
    current_preset = 'factory_default'
    """Name of the current configuration"""
    _conf_obj = False
    """Current configuration file path"""
    keepnames = []
    """Option names which should not be overwritten by a load/merge/update operation."""
    factory_default = {}
    """Default configuration"""

    def __init__(self, conf_dir=''):
        option.Conf.__init__(self)
        if not conf_dir.endswith('/'):
            conf_dir += '/'
        self._conf_dir = conf_dir
        """Destination folder for this object"""
        self.preset_cache = {}

    def setKeep_names(self, kn, append=True):
        """Sets the keep names list. Option names which should not be overwritten upon load/merge/update."""
        if append:
            kn = list(set(self.keepnames + kn))
        self.keepnames = kn

    def getKeep_names(self):
        """Returns the keep names list. Option names which should not be overwritten upon load/merge/update."""
        return self.keepnames

    def get_preset(self):
        """Returns current configuration name"""
        self.listPresets()
        return self.current_preset

    def set_preset(self, preset):
        """Loads configuration preset named `preset` and returns its dictionary representation."""
        print 'set_preset', preset
        r = self.load(preset)
        self.listPresets()
        return r

    def listPresets(self):
        """Lists available configurations"""
        r = [
            'factory_default']   # configurazione predefinita (sempre disponibile)
        if os.path.exists(self.conf_dir):
            r += utils.listDirExt(self.conf_dir)
        self.sete('preset', {'handle': 'preset', 'name': 'Configuration Preset', 'priority': -1,
                             'current': self.current_preset, 'options': r, 'type': 'Preset'})
        self.presets = r
        return self.presets

    def setConf_dir(self, cd):
        """Set the folder containing configuration files"""
        if not cd.endswith('/'):
            cd += '/'
        self._conf_dir = cd
        if os.path.exists(cd):
            # Try to load a default.csv file
            self.load('default')
        else:
            # Recursively create the directory
            os.makedirs(cd)
        # Re-validate the entire configuration in order to assign correct KID
        # values
        self.validate()

    def getConf_dir(self):
        """Returns the configuration file folder"""
        return self._conf_dir
    conf_dir = property(getConf_dir, setConf_dir)

    def setConf_obj(self, obj):
        """Sets current configuration persistent object path."""
        self._conf_obj = obj

    def getConf_obj(self):
        """Returns current configuration persistent object path"""
        return self._conf_obj
    conf_obj = property(getConf_obj, setConf_obj)

    def write(self, filename):
        """Write configuration onto output file `filename`"""
        opt = option.CsvStore(filename)
        opt.desc = self.desc
        opt.write_file()

    def save(self, name=False):
        """Saves current configuration into a persistent object."""
        if not name:
            name = self.current_preset
        if not name:
            self.current_preset = 'default'
        if name == 'factory_default':
            self.log.error(
                'Attempt to write a system file: Action forbidden.\n', name)
            return 'FORBIDDEN'
        obj = os.path.join(self.conf_dir, name + params.conf_ext)
        if not os.path.exists(self.conf_dir):
            os.mkdir(self.conf_dir)
        self.write(obj)
        self.log.info('saved configuration', name, 'in:', obj)
        self.current_preset = name
        self._conf_obj = obj
        self.listPresets()
        self.preset_cache[name] = self.desc.copy()
        return 'Configuration saved: ' + name

    def remove(self, name=False):
        """Deletes the persistent object associated with the current configuration."""
        obj = self.conf_obj
        if name:
            obj = os.path.join(self.conf_dir, name + params.conf_ext)
            if name == 'factory_default':
                self.log.error(
                    'Attempt to delete a system file: Action forbidden.\n', obj)
                return 'FORBIDDEN'
        if not os.path.exists(obj):
            msg = 'Tempted to delete non existent file:', obj
            self.log.error(msg)
            return msg
        os.remove(obj)
        self.log.info('Deleted configuration:', name, 'in:', obj)
        self.listPresets()
        return 'Configuration deleted: ', name
    
    def rename(self, new_name=False, old_name=False, overwrite=False):
        msg, st = rename(new_name, old_name, overwrite, self._conf_obj, self._conf_dir, self.log)
        # If was the current 
        if st and old_name in (False, self.current_preset):
            self.current_preset = new_name 
            self._conf_obj = os.path.join(self._conf_dir, new_name + params.conf_ext)
            c = self.desc['preset'] 
            c['current'] = new_name
            self.desc['preset'] = c
        self.listPresets()
        return msg
        

    def merge_desc(self, desc):
        """Apply desc avoiding overwriting of type attributes and keepnames values"""
        if not desc:
            return False
        for handle, opt in desc.iteritems():
            if not self.desc.has_key(handle):
                # Discard any new option which is not user-defined (only Script
                # and Meta can be!)
                if opt['type'] not in ('Script', 'Meta'):
                    continue
                old = False
            else:
                # dirshelf does not support get(key,else)
                old = self.desc.get(handle)
            # Preserve keepnames
            if old and (handle in self.keepnames):
                opt = old
            # Migrate option (avoid changing type, etc)
            elif old:
                opt.migrate_from(old)
            # Overwrite
            self.desc[handle] = opt
        self.validate()
        return True

    def load(self, name=False, path=False):
        """Reads the configuration from a persistent preset named `name`, or from a custom file path `path`"""
        if not self.conf_dir.endswith('/'):
            self.conf_dir += '/'
        old_conf_obj = self.conf_obj
        kept = {}
        for kn in self.keepnames:
            if self.desc.has_key(kn):
                kept[kn] = self[kn]  # self.desc[kn]['current']

        # FIXME: remove, done by apply_desc
        def restore():
            """Restore kept options"""
            print 'RESTORING', kept, self.keepnames
            for k, v in kept.iteritems():
                self[k] = v
        if path:
            obj = path
            current_preset = 'unknown'
        elif name:
            if name == 'factory_default':
                self.current_preset = name
                print 'factory_default name:', self.desc['name']['factory_default']
                for k, v in self.desc.iteritems():
                    self.desc[k]['current'] = v['factory_default']
                restore()
                self._conf_obj = False
                self.log.info('Restored factory_defaut')
                return 'factory_default'
            else:
                obj = os.path.join(self.conf_dir, name + params.conf_ext)
            current_preset = name
        else:
            obj = self.conf_obj
            current_preset = self.current_preset
        if not os.path.exists(obj):
            self.log.info('Non-existent configuration file:', obj)
            return False
        try:
            # get actual file
            store = option.CsvStore(obj)
            # merge description
            self.merge_desc(store.desc)
            self.current_preset = current_preset
            self.listPresets()
            c = self.desc['preset']
            c['current'] = current_preset
            self.desc['preset'] = c
            self.conf_obj = obj
            restore()
            self.preset_cache[current_preset] = self.desc.copy()
            return obj
        except:
            self.log.info('Unable to load new configuration: %s\n Keeping previous configuration: %s' % (
                self.conf_obj, old_conf_obj))
            self.log.debug(format_exc())
            self.conf_obj = old_conf_obj
            restore()
            return False
        
    def read_preset(self, preset):
        if preset in self.preset_cache:
            return self.preset_cache[preset]
        preset_path = os.path.join(self.conf_dir, preset + params.conf_ext)
        if not os.path.exists(preset_path):
            return False
        store = option.CsvStore(preset_path)
        self.preset_cache[preset] = store.desc
        return store.desc
        
    def get_from_preset(self, opt, preset, extended=False):
        """Read value of option `opt` saved in `preset`"""
        result = self.read_preset(preset)
        if not result:
            return False
        if extended:
            return result[opt]
        return result[opt]['current']
    
    def set_to_preset(self, opt, preset, val, attr=False):
        """Sets option `opt` value to `val` in specified `preset`.
        It will not actually loading the preset or set the value in memory."""
        attr = attr or 'current'
        preset_path = os.path.join(self.conf_dir, preset + params.conf_ext)
        if not os.path.exists(preset_path):
            self.log.error('Preset does not exist: cannot save into', preset_path)
            return False
        store = option.CsvStore(preset_path)
        store.desc[opt][attr] = val
        self.preset_cache[preset] = store.desc
        store.write_file()
        return True
        
    
    def compare_presets(self, opt):
        """Returns a dictionary mapping preset names and `opt` values"""
        opt_dict = self.gete(opt)
        key = 'current'
        # In case of a RoleIO, get the configured destination option
        if opt_dict['type'] == 'RoleIO':
            key = 'options'
        res = {'***current***': opt_dict[key]} # preset_name: current opt value
        for preset_name in self.listPresets():
            preset_desc = self.read_preset(preset_name)
            if not preset_desc:
                continue
            if not preset_desc.has_key(opt):
                continue
            res[preset_name] = preset_desc[opt][key]
        return res
        
    
    
