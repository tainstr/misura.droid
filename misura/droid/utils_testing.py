import collections
import os
from tempfile import mkdtemp
from twisted.web import xmlrpc, server, static

from . import parameters as params

root_shared_memory_directory = '/dev/shm/misura_tests'
if not os.path.exists(root_shared_memory_directory):
    os.makedirs(root_shared_memory_directory)
params.set_rundir(mkdtemp(dir=root_shared_memory_directory))
# These parameters may influence the behavior of subsequent imports
params.no_cam_controls = True
params.utest = True
params.set_datadir(params.testdir + "storage/data/")
params.set_confdir(params.testdir + "storage/conf/")
params.storagedir = params.testdir + 'storage/'
params.baseStorageDir = params.storagedir

from .device import registry as registry
from .data import filebuffer
from . import utils
from . import share
from .service import addListeners



def setTimeScaling(on=1, factor=10):
    utils.time_scaled.value = int(on)
    utils.time_factor.value = float(factor)
    utils.doTimeStep(set=0)


def parallel(pa=None):
    """Enable or disable parallel computing and shared memory space."""
    setTimeScaling(0)
    registry.registry = None
    filebuffer.locker.unlock_all()
    filebuffer.FileBuffer.cache = collections.OrderedDict()
    if pa is None:
        return params.parallel_computing
    params.parallel_computing = pa
    if pa and not share.cache.started:
        share.set_dbpath()
        share.stop()
        share.init()
        registry.get_registry()
    else:
        share.stop()
        


def serve(main, port=3880):
    from twisted.internet import reactor
    xmlrpc.addIntrospection(main)
    web = static.File(params.webdir)
    web.putChild('RPC', main)
    site = server.Site(web)
    addListeners(reactor, site, main, port=port, logf=main.log.info)
#     reactor.run(installSignalHandlers=1)
    p = multiprocessing.Process(target=reactor.run)
    p.daemon = main._daemon_acquisition_process
    return p, main