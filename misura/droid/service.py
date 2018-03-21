#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#!/usr/bin/twistd -noy
"""Misura super server to start and manage other modules."""
# TODO: implement errors
import os
import sys
import multiprocessing
import pkg_resources

from twisted.internet import defer, ssl
from twisted.web import xmlrpc, server, static
from twisted.protocols.ftp import FTPFactory,  BaseFTPRealm
from twisted.cred import credentials, checkers, error as credError
from twisted.cred.portal import Portal, IRealm
from twisted.web.guard import HTTPAuthSessionWrapper, DigestCredentialFactory, BasicCredentialFactory
from twisted.web.resource import IResource
from zope.interface import implements

from misura.canon import logger
from misura.droid import parameters as params
from misura.droid import share
from misura.droid import utils
from misura.droid.server import MainServer, MisuraDirectory, cert_dir


# Extract certificates from pkg_resources
# TODO: alternatively import from config dir
ssl_private_key = pkg_resources.resource_filename(
    'misura.droid.server', 'privkey.pem')
ssl_cacert = pkg_resources.resource_filename(
    'misura.droid.server', 'cacert.pem')
version_file = pkg_resources.resource_filename(
    'misura.droid', 'VERSION')
params.ssl_enabled = params.ssl_enabled and os.path.exists(
    ssl_private_key) and os.path.exists(ssl_cacert)
params.ssl_private_key = ssl_private_key
params.ssl_cacert = ssl_cacert
params.version_file = version_file


class UsersChecker:

    """Dummy password checker relying on the MainServer.users object."""
    # FIXME: Re-organize this part!
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (
        credentials.IUsernamePassword, credentials.IUsernameHashedPassword)

    def __init__(self, users):
        self.users = users

    def requestAvatarId(self, credentials):
        ok, msg = self.users.auth(credentials)

        if ok:
            return defer.succeed(msg)

        return defer.fail(
            credError.UnauthorizedLogin(msg))


class MisuraRealm(object):

    """Dummy realm returning the Misura main resource."""
    implements(IRealm)
    resource = None

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return (IResource, self.resource, lambda: None)
        raise NotImplementedError()


class MisuraFTPRealm(BaseFTPRealm):

    def getHomeDirectory(self, *a, **k):
        return self.anonymousRoot


def setMain(opt):
    """Create a MainServer class based on `opt` options"""
    instanceName = opt['-n']
    if not instanceName:
        instanceName = ''
    print 'setMain', opt
    # Determine logfile path into datadir
    log_filename = params.log_filename if not opt.has_key(
        '-d') else os.path.join(opt['-d'], 'log', 'misura.log')
    params.log_filename = log_filename
    # Start the object sharing process
    share.init(connect=False, log_filename=log_filename)
    # Instantiate mainserver class
    main = MainServer(instanceName=instanceName,
                      port=opt['-p'],
                      confdir=opt['-c'],
                      datadir=opt['-d'],
                      plug=opt['-e'],
                      manager=share.manager)
    xmlrpc.addIntrospection(main)
    mimetypes = {'.h5': 'application/x-hdf;subtype=bag'}
    static.File.contentTypes.update(mimetypes)
    web = static.File(params.webdir)
    web.putChild('RPC', main)
    web.putChild('data', static.File(params.datadir))
    web.putChild('conf', static.File(params.confdir))
    # StreamServer
    mdir = MisuraDirectory(main)
    web.putChild('stream', mdir)

    # Further reading about auth stuff:
    # http://www.tsheffler.com/blog/?p=502
    realm = MisuraRealm()
    realm.resource = web
    # TODO: use also for FTP!
    checker = UsersChecker(main.users)
    portal = Portal(realm, [checker])
    cred_methods = (DigestCredentialFactory(
        "md5", "MISURA"), BasicCredentialFactory('MISURA'))
    wrapper = HTTPAuthSessionWrapper(portal, cred_methods)
    site = server.Site(wrapper)
    return main, web, site


def addListeners(reactor, site, main, port=0, logf=False):
    """Add services"""
    # Simple logging
    if not logf:
        logf = logger.log.info
    if params.ssl_enabled:
        sslContext = ssl.DefaultOpenSSLContextFactory(
            ssl_private_key,
            ssl_cacert,)
        reactor.listenSSL(port, site, contextFactory=sslContext)
        logf('Misura Server Listening on SSL port:', port)
        logf('Using CA Certificate on:', ssl_cacert)
        logf('using private key on:', ssl_private_key)
    else:
        print 'SSL Disabled by parameters:', params.ssl_enabled
        reactor.listenTCP(port, site)
        logf('Misura Server Listening on TCP port:', port)
        logf('SSL DISABLED')
    reactor.addSystemEventTrigger("before", "shutdown", main.shutdown)
    if share.rank > 0:
        return
    # Add FTP server capability
    checker = UsersChecker(main.users)
    ftp = Portal(MisuraFTPRealm(params.datadir), [checker])
    f = FTPFactory(ftp)
    ftp_port = 3821 + port - 3880
    reactor.listenTCP(ftp_port, f)
    logf('Misura FTP Server Listening on TCP port:', ftp_port)


def startInstance(instanceName='', port=params.main_port):
    main, web, site = setMain(instanceName, port)
    addListeners(reactor, site, main,  port=port, logf=main.log.info)
    main.log.critical(
        'MisuraServer Ready To Server, instance: ' + instanceName)
    p = multiprocessing.Process(target=reactor.run)
    p.daemon = True
    p.start()
    return p

base_plugins="""misura.droid.users.Users
misura.droid.storage.Storage
misura.droid.support.Support
#GROUP
"""

def getOpts():
    """-n Instance Name
    -p Instance Port
    -c Configuration directory
    -d Data directory
    -m Memory directory
    -r Reinit instrument name
    -e Plugins
    Returns a dictionary with defaults or expressed variables.
    """
    import getopt
    opts, args = getopt.getopt(sys.argv[1:], 'n:p:c:d:m:r:e:')
    print opts, args
    r = {'-n': False, '-p': params.main_port,
         '-c': False, '-d': False, '-m': False, '-r': '',
         '-e': False,
         'args': args}
    for opt, val in opts:
        if opt == '-p':
            val = int(val)
        if opt in ['-c', '-d', '-m'] and val is not False:
            val = val.strip('"')
            if not val.endswith(params.sep):
                val += params.sep
            if not os.path.exists(val):
                print "Non-existent path configured for %s: %s" % (opt, val)
#               val=False
        if opt in ['-e'] and val is not False:
            val=val.strip('"').replace(';','\n')
            val=base_plugins+val
        r[opt] = val
    for opt, val in r.iteritems():
        if opt == '-c' and val is False:
            print 'Setting default confdir', params.datadir
            val = params.confdir
        elif opt == '-d' and val is False:
            print 'Setting default datadir', params.datadir
            val = params.datadir
        elif opt == '-m' and val is False:
            print 'Setting default rundir', params.rundir
            val = params.rundir
        elif opt == '-e' and val is False:
            print 'Setting default extensions'
            r[opt] = False
        r[opt] = val
    return r

from subprocess import Popen
from commands import getoutput as go


def stop():
    """Kill other instances of MisuraServer"""
    pids = go("pgrep -f MisuraServer").split('\n')
    pid = str(os.getpid()), str(os.getppid())

    print 'My pid', pid, pids
    for p in pids:
        if p in pid:
            continue
        print 'Killing pid:', p
        print go('kill -9 {}'.format(p))
    print 'Stopping tests:', go('pkill -9 -f test_')


def run(noname=False, misuraServerExe=params.misuraServerExe):
    global main, web, site
    # command-line start
    r = getOpts()
    if 'stop' in r['args']:
        stop()
        print 'All instances stopped. Exiting'
        return
    if 'restart' in r['args']:
        print 'Restarting...'
        stop()
    print 'Instance Name: %s; Port: %i\nConf: %s; Data: %s Mem: %s Ext: %s' % (r['-n'],
                                                                               r['-p'], r['-c'], r['-d'], r['-m'], r['-e'])
    params.set_confdir(r['-c'])
    params.set_datadir(r['-d'])
    params.set_rundir(r['-m'])
#   if (not noname) and r['-n'] is not False:
#       print 'SET INSTANCE NAME',  r['-n']
#       params.setInstanceName(r['-n'])
#   params.regenerateDirs()
    share.set_dbpath()
    main, web, site = setMain(r)
    # Re-initialize last instrument
    init_instrument = r['-r']
    if init_instrument:
        instrument = getattr(main, init_instrument, False)
        if not instrument:
            raise BaseException(
                'Asked to reinit an unexisting instrumnet! ' + init_instrument)
        instrument.init_instrument()
    from twisted.internet import reactor
    addListeners(
        reactor, site, main, port=r['-p'] + share.rank, logf=main.log.info)
    reactor.run(installSignalHandlers=1)
    # Stop remaining spares processes
    stop()
    utils.apply_time_delta(main.time_delta)
    # TODO: shell command to apply a time delta!
    if main.restart:
        args = sys.argv[1:]
        if main.reinit_instrument:
            args += ['-r', main.reinit_instrument]
        print 'RESTARTING', misuraServerExe, args
        # Make executable again, if upgraded in the meantime
        go('chmod ugo+x "{}"'.format(misuraServerExe))
        pid = Popen(["python", misuraServerExe] + args).pid
        print 'RESTARTED WITH PID', pid


if __name__ == '__main__':
    run()
