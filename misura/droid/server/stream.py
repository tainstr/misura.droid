# -*- coding: utf-8 -*-
"""Streaming resource for options"""
from time import sleep
import os
from twisted.web import resource, static,  server
from twisted.internet import interfaces
from zope.interface import implements


class OptionProducer(object):

    """A dummy producer which continously sends the current option value."""
    implements(interfaces.IPullProducer)

    def __init__(self, request, obj, opt, interval=0):
        self.request = request
        self.obj = obj
        self.opt = opt
        self.do = True
        self.interval = interval
        self.last = -1

    def header(self):
        """Send header"""
        self.request.setHeader("content-type", "text/plain; charset=utf-8")

    def start(self):
        """Register the producer into the reactor."""
        self.header()
        self.request.registerProducer(self, False)

    def stopProducing(self):
        self.request.unregisterProducer()
        self.request.finish()

    def pauseProducing(self):
        self.do = False

    def produce_value(self):
        """Get producible time,value. None,None if impossible to produce."""
        # interval disabled: notify upon each opt change
        t = self.obj.h_time_at(self.opt, -1)
        dt = (t - self.last) - self.interval
        if self.do and self.last > 0 and dt <= 0:
            # Avoid 100% CPU
            sleep(max(-dt, self.interval, 0.05))
            return None, None
        val = self.obj[self.opt]
        self.last = t
        return t, val

    def resumeProducing(self):
        """Called each time the reactor has time to send new value"""
        t, val = self.produce_value()
        if t is None:
            return
        print 'Writing ', t, val
        self.request.write(repr(val) + '\n')


class MultipartProducer(OptionProducer):
    boundary = 'ImageProducerBoundary'
    format = 'text/plain; charset=utf-8'

    def header(self):
        """Send a multipart header which will cause the content to be updated with new pages"""
        self.request.setHeader('transfer-encoding', '')
        self.request.setHeader('connection', 'close')
        self.request.setHeader(
            'cache-control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
        self.request.setHeader('pragma', 'no-cache')
        self.request.setHeader(
            "content-type", "multipart/x-mixed-replace; boundary=" + self.boundary)
        self.request.write('--' + self.boundary + '\r\n')

    def resumeProducing(self):
        t, frame = self.produce_value()
        if t is None:
            return
        inter = "Content-type: {}\r\nContent-length: {}\r\nX-Timestamp: {}\r\n\r\n".format(
            self.format, len(frame), t)
        self.request.write(inter)
        self.request.write(frame)
        self.request.write("\r\n--" + self.boundary + "\r\n")


class ImageProducer(MultipartProducer):

    """Producer for Image options which updates a multipart body."""
    # Inspired by:
    # http://sourceforge.net/p/mjpg-streamer/code/HEAD/tree/mjpg-streamer/plugins/output_http/httpd.c#l355
    format = 'image/jpeg'


class MisuraDirectory(resource.Resource):

    """Renders server object tree as a tabular folder of files.
    Adds updates streaming and large file uploads via POST requests."""

    def __init__(self, obj, node='stream'):
        resource.Resource.__init__(self)
        self.helper = static.DirectoryLister('')
        t = self.helper.template
        t = t.replace('Content encoding', 'Value').replace(
            'Filename', 'Name').replace('Size', 'Handle')
        self.helper.template = t
        self.obj = obj
        self.node = node

    def getChild(self, path, request):
        if path:
            # Remove /RPC/stream or /stream prefixes
            if path.startswith('/RPC'):
                path = path[4:]
            if path.startswith('/stream'):
                path = path[7:]
            sub = self.obj.child(path)
            if not sub:
                return self.childNotFound
            return MisuraDirectory(sub)
        else:
            return self

    @classmethod
    def check_POST(self, request):
        opt = request.args.get('opt', [False])[0]
        filename = request.args.get('filename', [False])[0]
        data = request.args.get('data', [False])[0]
        if False in (opt, filename, data):
            return False
        return opt, filename, data

    def render_POST(self, request):
        """Allows uploads via chunked post requests.
        Returns current file length."""
        r = self.check_POST(request)
        if r is False:
            return 'Invalid POST request'
        opt, filename, data = r
        if len(data) == 0:
            return 'No data for POST request'
        while '..' in filename:
            filename = filename.replace('..', '.')
        filename = filename.replace('/', '_')
        filename = os.path.join(self.obj.desc.getConf_dir(), opt, filename)
        print 'Writing file:', filename
        f = open(filename, 'ab+')
        # TODO: should lock files to avoid conflicts
        f.seek(0, 2)
        r0 = f.tell()
        f.write(data)
        f.seek(0, 2)
        r1 = f.tell()
        print 'Updated file:', filename, r0, r1
        return '{}->{}'.format(r0, r1)

    def render_GET(self, request):
        opt = request.args.get('opt', [False])[0]
        if opt:
            print 'Option requested:', opt
            i = request.args.get('interval', [0])[0]
            typ = self.obj.gete(opt)['type']
            if typ == 'Image':
                producer = ImageProducer(request, self.obj, opt, float(i))
            else:
                producer = OptionProducer(request, self.obj, opt, float(i))
            producer.start()
            return server.NOT_DONE_YET

        request.setHeader("content-type", "text/html; charset=utf-8")
        v = []
        dps = self.obj['fullpath']
        if dps == '/':
            dp0 = request.path
        else:
            dp0 = request.path.replace(dps, '')
            dp0 = dp0.replace('//', '/')

# 		dp0='./'+dps

        # List subdevices
        for d in self.obj.devices:
            dp = d['devpath']
            v.append({'text': d['name'], 'href': dp0 + '/' + dp,
                      'size': dp, 'type': '{' + d.__class__.__name__ + '}',
                      'encoding': ''})
        # List options
        for handle, opt in self.obj.describe().iteritems():
            url = dp0 + '?opt=' + handle
            desc = '[{}] {}'.format(handle, opt['name'])
            rep = repr(opt['current'])
            if len(rep) > 50:
                rep = rep[:46] + ' ...'
            v.append({'text': opt['name'], 'href': url,
                      'size': handle,
                      'type': opt['type'],
                      'encoding': repr(opt['current'])[:50]})
        tableContent = "".join(self.helper._buildTableContent(v))
        header = "Directory listing for " + self.obj['fullpath']
        print v
        r = self.helper.template % {
            "header": header, "tableContent": tableContent}
        r = r.encode('ascii', 'ignore')
        return r

    def close(self):
        for k, f in self.children.iteritems():
            print 'MisuraDirectory: closing', k
            f.close()
