#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Basic parameters and data structures"""
import os
import sys
from commands import getoutput as go
import pkg_resources
from traceback import print_exc

isWindows = os.name == 'nt'
sep = '\\' if isWindows else '/'
rootdir = 'C:\\' if isWindows else '/' 
version = 0  # Misura version
ut=False
# LOGIN
useAuth = True  # Require auth
exclusiveLogin = False  # Only 1 username at a time
loginDuration = 20  # Timeout after last operation
ssl_enabled = True

debug = True
utest = False  # unittesting environment
simulator = True  # Enable simulation of devices
real_devs = True  # Search for real devices
# +1        # multithreading initialization 
init_threads = False
# do not search for cameras (debug, for speed)
no_cam_controls = False
announceZeroconf = False
parallel_computing = True
managers_cache = 10
dummy_cameras = 2  # init dummy cameras (num >=0)

def determine_path(root=__file__):
    """Borrowed from wxglade.py"""
    try:
        #       root = __file__
        if os.path.islink(root):
            root = os.path.realpath(root)
        return os.path.dirname(os.path.abspath(root))
    except:
        print "I'm sorry, but something is wrong."
        print "There is no __file__ variable. Please contact the author."
        sys.exit()
# PATHS
home = os.path.expanduser("~") + sep
mdir = determine_path()  # Executable path
mdir += sep

misuraServerExe = os.path.join(mdir, 'MisuraServer.pyc')
baseStorageDir = os.path.join(home, 'storage', '')  # Config+Data
baseTmpDir = os.path.join(rootdir, 'tmp', 'misura', '')
baseRunDir = os.path.join(rootdir, 'dev','shm','misura','')
testdir = os.path.join(mdir, 'tests','')  # Test automatizzati


# Detect hardware mac address of this machine
if not isWindows:
    HW = go("ifconfig | grep 'HW' | awk '{ print $5}'|head -n1")
    # Check if netbooted - setup default dir in /opt/machines
    NETBOOTED = go('df -h|grep "/$"|grep ":/var/deploy" >/dev/null; echo $?')
    if NETBOOTED == '0':
        NETBOOTED = True
        baseStorageDir = "/opt/machines/" + HW + '/'
else:
    #TODO: how to find iface info on windows?
    HW = ''
    NETBOOTED = False

# LOGGING
log_basename = 'misura.log'
log_format = '%(levelname)s:%(asctime)s %(message)s'
log_disk_space = 1000 * (10 ** 6)  # Bytes (1GB)
log_file_dimension = 10 * (10 ** 6)  # Bytes (10MB)

# PORTS (only for standalone test instances)
main_port = 3880

# FILES
ext = '.h5'  # Misura test file extension
conf_ext = '.csv'
curve_ext = '.crv'
characterization_ext = '.csv'

fileTransferChunkLimit = 2  # MB
min_free_space_on_disk = 500  # MB
# lines. Max buffer length in per-device acquisition cycles
buffer_length = 100
buffer_dimension = 10 ** 6
MAX = 2 ** 32
MIN = 10 ** -10

# CAMERA ID
multisample_processing_pool = True
netusbcam = False +1
xiapi = False # +1
video4linux = False  +1



forbiddenID = []#['Laptop_Integrated_Webcam_3M', 'Integrated_Webcam_HD']

# SERIAL DEVICES
max_serial_scan = 5
enable_EurothermTr = True  # -1
enable_Eurotherm_ePack = True  # -1
enable_DatExel = True  # -1
enable_PeterNorbergStepperBoard = True  # -1
enable_TC08 = True -1

#######
# LOGIC #####################
#######
from multiprocessing import Value

# Extract certificates from pkg_resources
# TODO: alternatively import from config dir
# openssl genrsa 2048 > privkey.pem
# openssl req -new -x509 -sha512 -key privkey.pem -out cacert.pem -days 0
ssl_private_key = ''
ssl_cacert = ''
version_file = ''
try:
    ssl_private_key = os.path.join(mdir,'server','privkey.pem') 
    #pkg_resources.resource_filename('misura.droid.server', 'privkey.pem')
    ssl_cacert = os.path.join(mdir,'server','cacert.pem')
    #pkg_resources.resource_filename('misura.droid.server', 'cacert.pem')
except:
    print_exc()
ssl_enabled = True

ERRVAL = 2.**127
#######
# TESTING
#######
testing = False  # Impostato automaticamente dai test che lo richiedono

# Se in unittesting, non utilizzare funzionalità twisted

log_backup_count = int(1.*log_disk_space / log_file_dimension) + 1

# DERIVED PATHS
defaults = baseStorageDir
webdir = os.path.join(baseStorageDir, 'web', '')

# Will be redefined later
storagedir = baseStorageDir
confdir = storagedir
datadir = os.path.join(storagedir, 'data', '')
tmpdir = baseTmpDir
rundir = baseRunDir
logdir = os.path.join(datadir, 'log', '')
log_filename = os.path.join(logdir, log_basename)


def create_dirs(vd):
    for d in vd:
        if not os.path.exists(d):
            print 'Creating directory:', d
            os.makedirs(d)
            
# For new ssl certs:
# openssl genrsa 2048 > privkey.pem
# openssl req -new -x509 -sha512 -key privkey.pem -out cacert.pem -days 0


def set_confdir(cf):
    global confdir
    confdir = cf
    create_dirs([confdir])
    print 'set confdir', cf


def set_datadir(dd):
    global datadir, logdir, log_filename
    datadir = dd
    logdir = os.path.join(datadir, 'log', '')
    log_filename = logdir + log_basename
    create_dirs([datadir, logdir])
    print 'set datadir', dd


def set_rundir(rd):
    global rundir
    rundir = rd
    create_dirs([rundir])
    print 'set rundir', rd


def regenerateDirs():
    """Redefine and regenerate directories"""
    global confdir, datadir, logdir, log_filename, rundir
    confdir = storagedir
    vd = [tmpdir, rundir, os.path.join(tmpdir, 'profile')]
    datadir = os.path.join(storagedir, 'data', '')
    vd.append(datadir)
    logdir = os.path.join(datadir, 'log', '')
    vd.append(logdir)
    log_filename = os.path.join(logdir, log_basename)
    create_dirs(vd)


def setInstanceName(name=False):
    global storagedir, tmpdir, rundir
    if name:
        # FIXME: re-test, very old code! Must adapt also other dirs?
        storagedir += name + sep
        tmpdir += name + sep
        rundir += name + sep
        regenerateDirs()

regenerateDirs()
