from contextlib import closing
from time import gmtime
from tempfile import NamedTemporaryFile
from shutil import copyfileobj
from traceback import format_exc
from logging import getLogger

log = getLogger(__name__)

from zipstream import (
    ZipFile, ZIP_DEFLATED, ZIP_LZMA, ZipInfo, _get_compressor, crc32,
)


class FileWrapper(object):
    """A file object wrapper.

    Wrappers include information about what its stream's archive name should
    be and abstract how to get the stream and its length.

    """
    def __init__(self, arcname, fileobj):
        self._arcname = arcname
        self.fobj = fileobj

    @property
    def arcname(self):
        return self._arcname

    def get_stream(self):
        return self.fobj

    def __len__(self):
        tell = self.fobj.tell()
        self.fobj.seek(0, 2)
        size = self.fobj.tell()
        self.fobj.seek(tell)
        return size


class TempFileStreamingZipFile(ZipFile):
    """Streams wrappers in a zip.

    """
    def __init__(self, wrappers, mode='w', allowZip64=True, *args, **kwargs):
        super(TempFileStreamingZipFile, self).__init__(*args, **kwargs)
        for wrapper in wrappers:
            self.write(wrapper)

    def max_size(self):
        # 22 is the minimum size of a Zip EOCD
        max_size = 22
        for (wrapper,), kwargs in self.paths_to_write:
            content_len = len(wrapper)

            # https://en.wikipedia.org/wiki/Zip_(file_format)#File_headers
            # 88 = local file header (30) + central directory file header (46) +
            # possible data descriptor (12) + 
            # (arcname + null byte string terminator)
            # x2 once for the local header, once for the central directory
            max_size += 88 + (len(wrapper.arcname) + 1) * 2
            max_size += content_len
        return max_size

    def zinfo(self, st_mode, st_size, arcname, compress_type=None, date_time=None):
        """Create ZipInfo instance to store file information.

        """ 
        zinfo = ZipInfo(arcname, date_time)
        zinfo.external_attr = (st_mode & 0xFFFF) << 16      # Unix attributes
        if compress_type is None:
            zinfo.compress_type = self.compression
        else:
            zinfo.compress_type = compress_type

        zinfo.file_size = st_size
        zinfo.flag_bits = 0x00
        zinfo.flag_bits |= 0x08                 # ZIP flag bits, bit 3 indicates presence of data descriptor
        zinfo.header_offset = self.fp.tell()    # Start of header bytes
        if zinfo.compress_type == ZIP_LZMA:
            # Compressed data includes an end-of-stream (EOS) marker
            zinfo.flag_bits |= 0x02

        return zinfo

    def zinfo_from_wrapper(self, wrapper, compress_type=None, date_time=None):
        st_mode = 0644
        st_size = len(wrapper)

        if date_time is None:
            date_time = gmtime()

        return self.zinfo(
            st_mode, st_size, wrapper.arcname, compress_type, date_time)

    def _arcname_from_stat(self, filename, isdir, arcname=None):
        if arcname is None:
            arcname = filename
        arcname = os.path.normpath(os.path.splitdrive(arcname)[1])
        while arcname[0] in (os.sep, os.altsep):
            arcname = arcname[1:]
        if isdir:
            arcname += '/'
        return arcname

    def zinfo_from_stat(self, st, isdir, arcname, compress_type=None):
        mtime = time.localtime(st.st_mtime)
        date_time = mtime[0:6]
        return self.zinfo(st[0], st.st_size, arcname, compress_type, date_time)

    def _file_to_bytes(self, fp, zinfo):
        """Yield the bytes for the file object in the zip.""" 
        cmpr = _get_compressor(zinfo.compress_type)

        # Must overwrite CRC and sizes with correct data later
        zinfo.CRC = CRC = 0
        zinfo.compress_size = compress_size = 0
        # Compressed size can be larger than uncompressed size
        zip64 = self._allowZip64 and \
                zinfo.file_size * 1.05 > ZIP64_LIMIT
        yield self.fp.write(zinfo.FileHeader(zip64))
        file_size = 0
        while 1:
            buf = fp.read(1024 * 8)
            if not buf:
                break
            file_size = file_size + len(buf)
            CRC = crc32(buf, CRC) & 0xffffffff
            if cmpr:
                buf = cmpr.compress(buf)
                compress_size = compress_size + len(buf)
            yield self.fp.write(buf)

        if cmpr:
            buf = cmpr.flush()
            compress_size = compress_size + len(buf)
            yield self.fp.write(buf)
            zinfo.compress_size = compress_size
        else:
            zinfo.compress_size = file_size
        zinfo.CRC = CRC
        zinfo.file_size = file_size
        if not zip64 and self._allowZip64:
            if file_size > ZIP64_LIMIT:
                raise RuntimeError('File size has increased during compressing')
            if compress_size > ZIP64_LIMIT:
                raise RuntimeError('Compressed size larger than uncompressed size')

        # Seek backwards and write file header (which will now include
        # correct CRC and file sizes)
        # position = self.fp.tell()       # Preserve current position in file
        # self.fp.seek(zinfo.header_offset, 0)
        # self.fp.write(zinfo.FileHeader(zip64))
        # self.fp.seek(position, 0)
        yield self.fp.write(zinfo.DataDescriptor())
        self.filelist.append(zinfo)
        self.NameToInfo[zinfo.filename] = zinfo

    def _ZipFile__write(self, wrapper_or_name, zinfo=None, arcname=None,
                compress_type=None, date_time=None):
        """Put the bytes from filename into the archive under the name
        arcname."""
        if not self.fp:
            raise RuntimeError(
                  "Attempt to write to ZIP archive that was already closed")

        if isinstance(wrapper_or_name, basestring):
            st = os.stat(wrapper_or_name)
            isdir = stat.S_ISDIR(st.st_mode)
            zinfo = self.zinfo_from_filename(
                st, isdir,
                self._arcname_from_stat(wrapper_or_name, isdir, arcname),
                compress_type)
        else:
            if wrapper_or_name.arcname is None:
                # Cannot write without archive name
                return

            try:
                zinfo = self.zinfo_from_wrapper(
                    wrapper_or_name, compress_type, date_time)
            except Exception as exc:
                log.error(u'Unable to get ZipInfo: {0!r}'.format(
                    format_exc(exc)))
                return
            isdir = False

        self._writecheck(zinfo)
        self._didModify = True

        if isdir:
            zinfo.file_size = 0
            zinfo.compress_size = 0
            zinfo.CRC = 0
            self.filelist.append(zinfo)
            self.NameToInfo[zinfo.filename] = zinfo
            yield self.fp.write(zinfo.FileHeader(False))
            return

        if isinstance(wrapper_or_name, basestring):
            fp = open(wrapper_or_name, 'rb')
        else:
            fp = wrapper_or_name.get_stream()

            if not fp:
                # Cannot write non-stream
                return
        try:
            for chunk in self._file_to_bytes(fp, zinfo):
                yield chunk
        finally:
            fp.close()
