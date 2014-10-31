=================
tempfilezipstream
=================

The zipstream package provides functionality to stream zip files from the local
filesystem. This package extends ZipStream to be able to stream file objects
through the use of temporary files.

Concepts
========

FileWrapper
-----------

All file objects to be streamed should be wrapped. A file wrapper must define 

  1. arcname or the name that the file will have in the archive
  2. a way to get the file object's size, len()
  3. a way to get the file object, get_stream()

len() and get_stream() are separated because getting the stream could be a
significantly more expensive way to get the size.

TempFileZipStream
-----------------

Initialize this object with a list of wrappers to be streamed. It knows how to
calculate the max_size() that the zip archive will take. Obviously, this is a
best estimate and likely the worst case.

