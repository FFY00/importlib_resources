from __future__ import absolute_import

import io
import abc
import itertools

from ._compat import ABC, FileNotFoundError

# Use mypy's comment syntax for Python 2 compatibility
try:
    from typing import BinaryIO, Iterable, Text
except ImportError:
    pass


class ResourceReader(ABC):
    """Abstract base class for loaders to provide resource reading support."""

    @abc.abstractmethod
    def open_resource(self, resource):
        # type: (Text) -> BinaryIO
        """Return an opened, file-like object for binary reading.

        The 'resource' argument is expected to represent only a file name.
        If the resource cannot be found, FileNotFoundError is raised.
        """
        # This deliberately raises FileNotFoundError instead of
        # NotImplementedError so that if this method is accidentally called,
        # it'll still do the right thing.
        raise FileNotFoundError

    @abc.abstractmethod
    def resource_path(self, resource):
        # type: (Text) -> Text
        """Return the file system path to the specified resource.

        The 'resource' argument is expected to represent only a file name.
        If the resource does not exist on the file system, raise
        FileNotFoundError.
        """
        # This deliberately raises FileNotFoundError instead of
        # NotImplementedError so that if this method is accidentally called,
        # it'll still do the right thing.
        raise FileNotFoundError

    @abc.abstractmethod
    def is_resource(self, path):
        # type: (Text) -> bool
        """Return True if the named 'path' is a resource.

        Files are resources, directories are not.
        """
        raise FileNotFoundError

    @abc.abstractmethod
    def contents(self):
        # type: () -> Iterable[str]
        """Return an iterable of entries in `package`."""
        raise FileNotFoundError


class Traversable(ABC):
    """
    An object with a subset of pathlib.Path methods suitable for
    traversing directories and opening files.
    """

    @abc.abstractmethod
    def iterdir(self):
        """
        Yield Traversable objects in self
        """

    def read_bytes(self):
        """
        Read contents of self as bytes
        """
        with self.open('rb') as strm:
            return strm.read()

    def read_text(self, encoding=None):
        """
        Read contents of self as text
        """
        with self.open(encoding=encoding) as strm:
            return strm.read()

    @abc.abstractmethod
    def is_dir(self):
        """
        Return True if self is a dir
        """

    @abc.abstractmethod
    def is_file(self):
        """
        Return True if self is a file
        """

    @abc.abstractmethod
    def joinpath(self, child):
        """
        Return Traversable child in self
        """

    def __truediv__(self, child):
        """
        Return Traversable child in self
        """
        return self.joinpath(child)

    @abc.abstractmethod
    def open(self, mode='r', *args, **kwargs):
        """
        mode may be 'r' or 'rb' to open as text or binary. Return a handle
        suitable for reading (same as pathlib.Path.open).

        When opening as text, accepts encoding parameters such as those
        accepted by io.TextIOWrapper.
        """


class SimpleReader(ABC):

    @abc.abstractproperty
    def package(self):
        """
        The name of the package for which this reader loads resources.
        """

    @abc.abstractmethod
    def child_readers(self) -> ['SimpleReader']:
        """
        Obtain an iterable of ResourceReader for available
        child virtual packages of this one.
        """

    @abc.abstractmethod
    def resources(self) -> [str]:
        """
        Obtain available named resources for this virtual package.
        """

    @abc.abstractmethod
    def open_binary(self, resource) -> BinaryIO:
        """
        Obtain a File-like for a named resource.
        """

    @property
    def name(self):
        return self.package.split('.')[-1]


class TraversableResources(ResourceReader):
    @abc.abstractmethod
    def files(self):
        """Return a Traversable object for the loaded package."""

    def open_resource(self, resource):
        return self.files().joinpath(resource).open('rb')

    def resource_path(self, resource):
        raise FileNotFoundError(resource)

    def is_resource(self, path):
        return self.files().joinpath(path).isfile()

    def contents(self):
        return (item.name for item in self.files().iterdir())


class ResourceHandle(Traversable):
    def __init__(self, reader, name):
        self.reader = reader
        self.name = name

    def is_file(self):
        return True

    def is_dir(self):
        return False

    def open(self, mode='r', *args, **kwargs):
        stream = self.reader.open_binary(self.name)
        if 'b' not in mode:
            stream = io.TextIOWrapper(*args, **kwargs)
        return stream


class ResourceContainer(Traversable):
    def __init__(self, reader: SimpleReader):
        self.reader = reader

    def is_dir(self):
        return True

    def is_file(self):
        return False

    def iterdir(self):
        files = (
            ResourceHandle(self, name)
            for name in self.resources
            )
        dirs = map(ResourceContainer, self.child_readers())
        return itertools.chain(files, dirs)

    def open(self, *args, **kwargs):
        raise IsADirectoryError()

    def joinpath(self, name):
        return next(
            traversable
            for traversable in self.iterdir()
            if traversable.name == name)


class TraversableReader(TraversableResources, SimpleReader):
    def files(self):
        return ResourceContainer(self)
