#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Tree-aware interface"""
from copy import deepcopy
import os
from traceback import print_exc

from misura.canon import option

from misura.droid import parameters as params
from misura.droid import data
from configuration import ConfigurationInterface,  NoProperty


# FIXME: should extend this to EVERY method/attribute of ANY class
# deriving from Node...!!!! unfeasible.
forbidden_node_names = ['system', 'parent', 'child', 'desc', 'idesc']


class Node(ConfigurationInterface):

    """Tree-aware and implicit desc class"""
    conf_def = deepcopy(ConfigurationInterface.conf_def)
    conf_def += [{"handle": 'fullpath', "name": 'Full object path',
                  "current": 'node',    "type": 'ReadOnly', "attr": ['Hidden']},
                 {"handle": 'devpath', "name": 'Object node name',
                  "current": 'node',    "type": 'ReadOnly', "attr": ['Hidden']},
                 {"handle": 'dev',  "name": 'Physical device node',
                  "current": 'none',    "type": 'ReadOnly', "attr": ['Hidden']}
                 ]
    naturalName = 'node'
    _Method__name = None  # Client-side compatibility for testing purposes
    _parent = None
    _root = None

    @classmethod
    def query_udev(cls, node=None):
        """Calculate and return the unique devpath 
        for a possible instance of this class.
        Returns also other path-dependant properties in a dictionary."""
        if node in [None, '', False]:
            devpath = cls.naturalName
            dev = devpath
        else:
            dev = node
            devpath = node
        return {'devpath': devpath, 'dev': dev}

    def parent(self):
        return self._parent

    @property
    def root(self):
        """Do a reversal search in order to find the root of the object tree"""
        # Cached result
        if self._root is not None:
            return self._root
        parent = self.parent()
        # Search upwards
        while parent is not None:
            if parent.parent() is None:
                break
            parent = parent.parent()
        self._root = parent
        return parent

    @property
    def root_obj(self):
        """Operative root object. Same as root, but returns self instead of None"""
        if self.root is None:
            return self
        return self.root

    def __init__(self, parent=None, node='node'):
        """Tree-aware"""
        # Assure that each instance gets its own, unique, configuration
        # definition
        self.roledev = {}
        """Role->Dev mapping dictionary"""
        if node in forbidden_node_names:
            print 'Forbidden node name', node
            return
        self.conf_def = deepcopy(self.conf_def)
        self._parent = parent
        # import here so we get fresh database definition
        from misura.droid import share
        if self.root is None:
            manager = share.manager
            self.main_confdir = params.confdir
        else:
            manager = self.root.manager
            self.main_confdir = self.root.main_confdir
        self.manager = manager
        # Create Conf object
        conf_dir = self.main_confdir + self.__class__.__name__
        ddesc = option.ListStore.read(self.conf_def)
        desc = data.Conf(desc=ddesc, conf_dir=conf_dir)
        desc.set_current('dev', node)
        desc.set_current('devpath', node)
        ConfigurationInterface.__init__(self, desc)

        self.idesc = ConfigurationInterface(self.desc)
        """Pure XMLRPC interface to the configuration object (skipping all get/set layers)"""
        self.putSubHandler('desc', self.idesc)
        # Set query_udev results (and also devpath, dev)
        udev = self.query_udev(node)
        for k, v in udev.iteritems():
            if not self.desc.has_key(k):
                print 'skipping queryudev key', k, v
                continue
            self[k] = v
        self.desc.setKeep_names(['dev', 'devpath', 'fullpath'])
        self.naturalName = self.desc.get('devpath')
        self.attach(self.parent())
        # Set the persistent folder
        conf_dir = '%s%s' % (self.main_confdir, self['fullpath'].lstrip('/'))
        self.desc.setConf_dir(conf_dir)
        # Create full directory tree
        bdir = ''
        for cdir in conf_dir.split('/'):
            bdir += '/' + cdir
            if not os.path.exists(bdir):
                os.mkdir(bdir)

    def attach(self, parent, idx=-1):
        """Attach the device to `parent` node"""
        self._parent = parent
        parent = self.parent()
        if parent is None:
            self.log.error('No parent', self.desc.get('devpath'), repr(self))
            return False
        dp = self['devpath']
        if not dp:
            self.log.error(
                'No device path to attach', self['devpath'], repr(self))
            return False
        setattr(parent, dp, self)
        parent.putSubHandler(dp, self)
        if idx < 0:
            idx = len(parent.devices)
        parent.devices.insert(idx, self)
        self.idx = idx
        parent._rmodel = False  # ?
        return True

    def get_fullpath(self):
        """Calculate full object path"""
        po = self
        path = []
        while True:
            # Stop at root
            if po['devpath'] == 'MAINSERVER':
                break
            # Stop at orphan objects (used in unittests)
            if (po.parent() == None):
                break
            dp = po['devpath']
            path.append(dp if dp else '?')
            po = po.parent()
            if po in [None, False]:
                break
        # Revert to get the top-down path
        path.reverse()
        p = '/'
        if len(path) > 0:
            p += '/'.join(path) + '/'
        op = self.desc.get('fullpath')
        if p != op:
            self._Method__name = p
            self.desc.set('fullpath', p)
            self.desc.kid_base = p
            self.desc.validate()
        return p

    def close(self):
        """Closes the object and any associated resource.
        Removes any references in the tree."""
        print 'Node.close', type(self), id(self)
        if self.desc is False:
            print 'Node.close no desc',  type(self), id(self)
            return False
        if self.desc.dir is False:
            print 'Already closed'
            return False
        if not os.path.exists(self.desc.dir):
            print 'Already deleted', self.desc.dir
            return False
        print 'detaching', self.desc.dir
        self.detach()
        for k, v in self.subHandlers.items():
            if v is self:
                continue
            if k in forbidden_node_names:
                continue
            print 'Closing sub handler', k
            try:
                v.close()
            except:
                print_exc()
        self.idesc = self
        ConfigurationInterface.close(self)
        return True

    def detach(self):
        """Detach the device from its parent.
        Returns the index the device had in parent.devices list."""
        # Remove references to old object location in tree
        i = -1
        p = self.parent()
        if p is None:
            return i
        if self.desc.dir is False:
            return i
        try:
            odp = self['devpath']
        except NoProperty:
            print 'failed detach', type(self), id(self)
            return i
        if odp != '':
            ci = getattr(p, odp, False)
            if ci is not False:
                delattr(p, odp)
        # Remove any subhandler mapped to self from parent
        myid = id(self)
        idx = [id(obj) for obj in p.subHandlers.values()]
        if myid in idx:
            i = idx.index(myid)
            k = p.subHandlers.keys()[i]
            print 'Removing subHandler', k
            del p.subHandlers[k]
        # Remove from parent's devices list
        idx = [id(obj) for obj in p.devices]
        if myid in idx:
            i = idx.index(myid)
            print 'Removing device', i
            p.devices.pop(i)
        self._parent = None
        return i

    def list(self):
        """List children Devices, if existing, in [(name,naturalName)] tuples"""
        r = []
        for dev in self.devices:
            dp = dev['devpath']
            print 'list', dp, dev['name']
            r.append(   (dev.get('name', dp), dp)   )
        return r
    xmlrpc_list = list

    def has_child(self, name):
        """Returns if `name` is a subhandler"""
        return self.subHandlers.has_key(name)
    xmlrpc_has_child = has_child

    def flatten(self, lst=False):
        """Returns a flat list of all subdevices and their children devices, iteratively."""
        if lst is False:
            lst = []
        for d in self.devices:
            if d is self:
                continue
            lst.append(d)
            lst = d.flatten(lst)
        return lst

    def search_opt(self, handle, equals):
        """Search for subdevice which option `handle` value exists and is equal to `equals`."""
        for dev in self.devices:
            if not dev.has_key(handle):
                continue
            if dev[handle] == equals:
                return dev
        return False

    def searchPath(self, fullpath0, devlist=False):
        """Retrieve the subdevice having the desired fullpath.
        Returns False if no subdevice exists or the fullpath cannot stem from this node.
        """
        if fullpath0 == '.':
            return self['fullpath']
        if fullpath0 in ['None', 'none']:
            print 'searchPath: asked for None'
            return False
        sfp = self['fullpath'].replace('//', '/')
        if not fullpath0.startswith(sfp):
            self.log.error(
                'searchPath error: not corresponding', fullpath0, sfp)
            return False
        # Cut the full path where itself is found
        fullpath = fullpath0[len(sfp):].split('/')[:-1]
#       print 'searchPath: analyzing',fullpath0,fullpath
        # Verify existence
        obj = self
        for p in fullpath:
            obj = obj.subHandlers.get(p, False)
            if not obj:
                self.log.error('searchPath: not found!', fullpath0, fullpath)
                return False
#       print 'SearchPath: returning',fullpath
        if not len(fullpath):
            return self['fullpath']
        return '/'.join(fullpath)

    def xmlrpc_searchPath(self, *a, **k):
        r = self.searchPath(*a, **k)
        return r

    def toPath(self, path):
        """Returns the child object having the desired path"""
        path0 = path
        if isinstance(path, str):
            path = path.split(self.separator)
        # Clean path
        if len(path) > 0 and path[-1] == '':
            path.pop(-1)
        if len(path) > 0 and (path[0] == ''):
            path.pop(0)
        
        for dev in self['fullpath'].split(self.separator):
            if dev=='':
                continue
            if path==dev:
                path.pop(0)
            else:
                break
        
        obj = self
        for p in path:
            obj = obj.subHandlers.get(p, False)
            if not obj:
                self.log('Error retrieving path', path0, path, p)
                return None
        return obj

    def child(self, *a, **k):
        """Same as toPath"""
        return self.toPath(*a, **k)

    def read_kid(self, k):
        """Returns referred object and option name for kid path `k`."""
        if k != '/':
            k = k.split('/')
        n = k.pop(-1)
        if len(k) <= 1:
            obj = self
        else:
            p = self.root.searchPath('/'.join(k) + '/')
            if not p:
                self.log.debug('Object not found:', k)
                return False, n
            obj = self.root.child(k)
            if not obj:
                self.log.debug('Child object not found', k)
                return False, n
        if not obj.has_key(n):
            self.log.debug('Option not found:', n, k)
            return False, n
        return obj,  n

    def xmlrpc_read_kid(self, k, readLevel=5):
        """debug"""
        if readLevel < 5:
            return 'NO AUTH'
        obj, n = self.read_kid(k)
        if not obj:
            return 'NO OBJECT', k
        return obj[n]

    def get_idx(self):
        """Return the index in the parent devices list"""
        return self.idx

    def tree(self, level=1, msg='root\n'):
        """Builds a configuration tree with all child descriptions"""
        out = {'self': self.describe()}
        pref = self.getSubHandlerPrefixes()
        pref = [d['devpath'] for d in self.devices]
#       print 'Subhandler prefixes',pref
        # Find real object names
        childs = {}
        for p in pref:
            if p == 'desc':
                continue
            obj = self.getSubHandler(p)
            if childs.has_key(obj):
                # Better name than automatic names:
                if childs[obj].startswith('idx'):
                    print 'Substituting name:', childs[obj], p
                    childs[obj] = p
            else:
                childs[obj] = p

        for obj, p in childs.iteritems():
            if not getattr(obj, 'tree', False):
                continue
            msg += '   ' * level + '|--> ' + p + '\n'
            out[p], msg = obj.tree(level=level + 1, msg=msg)
#       if level==1:
#           print msg
        return out, msg
