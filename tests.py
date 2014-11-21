import types
from unittest import TestCase
from StringIO import StringIO
import logging
from time import sleep, time

from tempfilezipstream import TempFileStreamingZipFile, FileWrapper

log = logging.getLogger(__name__)


def get_all(iterable):
    bytes_ = []
    try:
        while True:
            bytes_.append(iterable.next())
    except StopIteration:
        pass
    return ''.join(bytes_)


class DelayFile(object):

    def __init__(self, sleep=0.1):
        self.sleep = sleep
        self.closed = False
        self.head = 0

    def seek(self, target, offset=0):
        if offset == 2:
            self.head = max(8 - target, 0)
        else:
            self.head = target

    def tell(self):
        return self.head

    def read(self, size=-1):
        sleep(self.sleep)
        if self.closed:
            return ""
        self.closed = True
        return "contents"

    def close(self): pass


class TestUnit(TestCase):

    def test_immediacy(self):
        sleep = 0.1
        szip = TempFileStreamingZipFile([
            FileWrapper('namea', DelayFile(sleep)),
            FileWrapper('nameb', DelayFile(sleep)),
        ])
        zfile = iter(szip)
        then = time()
        chunk = zfile.next()
        delta = time() - then
        # The iter should start streaming first file almost immediately rather
        # than waiting to buffer both files.
        self.assertLessEqual(delta, sleep * 2)

    def test_zip_load(self):
        szip = TempFileStreamingZipFile([])
        zfile = iter(szip)
        self.assertTrue(isinstance(zfile, types.GeneratorType))
        contents = get_all(zfile)
        self.assertEqual(len(contents), 22)
        self.assertTrue(contents[:2], 'PK')

        # None arcname is skipped
        ddd = StringIO('do not care')
        arcname = None
        szip = TempFileStreamingZipFile([FileWrapper(arcname, ddd)])
        zfile = iter(szip)
        contents = get_all(zfile)
        self.assertEqual(len(contents), 22)

        # None fileobj is skipped
        arcname = 'namea'
        szip = TempFileStreamingZipFile([FileWrapper(arcname, None)])
        zfile = iter(szip)
        contents = get_all(zfile)
        self.assertEqual(len(contents), 22)

        data = 'http://999.0.0.0'
        ddd = StringIO(data)
        arcname = 'namea'
        szip = TempFileStreamingZipFile([FileWrapper(arcname, ddd)])
        zfile = iter(szip)
        contents = get_all(zfile)
        self.assertTrue(contents[:2], 'PK')
        # TODO Not quite sure why there's 2 extra bytes yet.
        self.assertLessEqual(len(contents),
                             22 + 88 + (len(arcname) + 1) * 2 + len(data) + 2)

    def test_zip_max_size(self):
        szip = TempFileStreamingZipFile([])
        self.assertEqual(szip.max_size(), 22)

        data = 'data:text/html,'
        ddd = StringIO(data)
        arcname = 'namea'
        szip = TempFileStreamingZipFile([FileWrapper(arcname, ddd)])
        self.assertEqual(
            szip.max_size(),
            22 + 88 + (len(arcname) + 1) * 2 + len(data))

