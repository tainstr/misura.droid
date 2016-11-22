# -*- coding: utf-8 -*-
"""Server-side SharedFile implementation for runtime data collection."""
from traceback import print_exc
import hashlib

from Crypto.PublicKey import RSA
import Crypto.Hash.SHA as SHA
import Crypto.Signature.PKCS1_v1_5 as PKCS1_v1_5

from misura.canon import indexer
from ..utils import lockme
from .. import parameters as params

from refupdater import ReferenceUpdater


def sign(f, cacert=False, privkey=False):
    """Digitally sign a file using server's private key."""
    # TODO: use config options?
    # Save public certificate
    if not cacert:
        cacert = params.ssl_cacert
    f.root.conf.attrs.cert = open(cacert, 'r').read()
    # Read the certificate
    if not privkey:
        privkey = params.ssl_private_key
    private_key = open(privkey, 'r').read()
    # Create the key
    key = RSA.importKey(private_key)
    verifier = PKCS1_v1_5.new(key)
    # Public key
    public_key = key.publickey()
    f.root.conf.attrs.public_key = public_key.exportKey()
    print 'PubKey', public_key, f.root.conf.attrs.public_key

    data = indexer.calc_hash(f)

    # Create message digest
    h = SHA.new(data)
    # Create the signature
    signature = verifier.sign(h)
    f.root.conf.attrs.signature = signature
    f.flush()
    return True


class OutputFile(indexer.SharedFile):

    """Server-side SharedFile implementation for runtime data collection."""
    updater = False
    stopped = False
    
    def __init__(self, *a, **kw0):
        print 'OutputFile', kw0
        kw = kw0.copy()
        dbpath = kw.pop('shm_path')
        zerotime = kw.pop('zerotime')
        indexer.SharedFile.__init__(self, *a, **kw)
        if None not in [dbpath, zerotime]:
            self.set_updater(dbpath, zerotime)
        
        
    def set_updater(self, dbpath, zerotime=-1):
        if self.updater:
            print 'Closing existing updater'
            self.updater.close()
        print 'OutputFile.set_updater', dbpath, zerotime
        self.updater = ReferenceUpdater(dbpath,
                                        outfile=self,
                                        zerotime=zerotime)
        self.stopped = False

    def sync(self, zerotime=-1,  only_logs=False):
        try:
            return self.updater.sync(zerotime=zerotime,  only_logs=only_logs)
        except:
            print 'OutputFile.sync() ERROR'
            print_exc()
            return False

    def stop(self):
        """Close the updater threadpool."""
        if self.updater and not self.stopped:
            self.updater.close()
        self.stopped = True
        return True

    def close(self):
        """Implicitly call self.stop()"""
        self.stop()
        return indexer.SharedFile.close(self)

    @lockme
    def sign(self, cacert=False, privkey=False):
        return sign(self.test)
