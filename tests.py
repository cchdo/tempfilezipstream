import types
from unittest import TestCase
from StringIO import StringIO
import logging

from tempfilezipstream import TempFileStreamingZipFile, FileWrapper

log = logging.getLogger(__name__)


class TestUnit(TestCase):
    def test_zip_load(self):
        szip = TempFileStreamingZipFile([])
        zfile = iter(szip)
        self.assertTrue(isinstance(zfile, types.GeneratorType))
        contents = zfile.next()
        self.assertEqual(len(contents), 22)
        self.assertTrue(contents[:2], 'PK')

        # None arcname is skipped
        ddd = StringIO('do not care')
        arcname = None
        szip = TempFileStreamingZipFile([FileWrapper(arcname, ddd)])
        zfile = iter(szip)
        contents = zfile.next()
        self.assertEqual(len(contents), 22)

        # None fileobj is skipped
        arcname = 'namea'
        szip = TempFileStreamingZipFile([FileWrapper(arcname, None)])
        zfile = iter(szip)
        contents = zfile.next()
        self.assertEqual(len(contents), 22)

        data = 'http://999.0.0.0'
        ddd = StringIO(data)
        arcname = 'namea'
        szip = TempFileStreamingZipFile([FileWrapper(arcname, ddd)])
        zfile = iter(szip)
        contents = zfile.next()
        self.assertTrue(len(contents) <= 22 + (len(arcname) + 1) * 2 + len(data))

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

