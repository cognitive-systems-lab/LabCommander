import inspect
import logging
from pathlib import Path
import string
import sys
import uuid

import appdirs


try:
    import coloredlogs
    coloredlogs_available = True
except ImportError:
    coloredlogs_available = False

log = logging.getLogger(__name__)


CORE_SERVICE_PATH = Path(__file__).parent / "services"
USER_SERVICE_PATH = Path(appdirs.user_data_dir("labc")) / "services"


if sys.version_info < (3,9):
    """
    Add is_relative_to function to pathlib.Path class, which was only added in python 3.9
    """
    def is_relative_to(self, *other):
        try:
            self.relative_to(*other)
            return True
        except ValueError:
            return False
    Path.is_relative_to = is_relative_to
    del is_relative_to

def quantify_scope(scope: str):
    if scope == "network":
        return 3
    elif scope == "host":
        return 2
    elif scope == "server":
        return 1
    else:
        return 0


def isinstance_namedtuple(obj) -> bool:
    return (
            isinstance(obj, tuple) and
            hasattr(obj, '_asdict') and
            hasattr(obj, '_fields')
    )


def print_as_table(colnames, data,*, columns_by_name=True, replace_empty=None):
    # Headers, centered

    if isinstance(colnames, str):
        colnames = colnames.split()

    if columns_by_name and isinstance_namedtuple(data[0]):
        data = [[str(getattr(row, name)) for name in colnames] for row in data]
    else:
        data = [[str(field) for field in row] for row in data]
        
    col_lens = [max(map(len, col))+2 for col in zip(colnames, *data)]
    line_pattern = ["{:"+str(cl)+"s}" for cl in col_lens]
    line_pattern = ' '.join(line_pattern)
    header = line_pattern.format(*colnames)
    print(header)
    print('-'*(sum(col_lens)+3))

    # Lines
    # line_pattern = ["{:15s}"] + ["{: 15s}"]*(len(colnames)-1)
    #line_pattern = ' '.join(line_pattern)
    for line in data:
        line = map(str, line)
        if replace_empty is not None:
            line = (word if word else replace_empty for word in line)
        print(line_pattern.format(*line))


############################# Errors #############################

class RemoteError(Exception):
    pass


class RemoteNameError(RemoteError):
    """Raised when route could not be found on remote server."""
    pass


class RemoteCallError(RemoteError):
    """Raised when an exception was raised in an remote call."""
    pass


class RemoteEncodingError(RemoteError):
    """Raised when return value or remote functions could not be json-encoded."""
    pass

class ResolutionError(Exception):
    """Raised when client could not resolve a server for a given name."""
    pass


################# Classes, Instances, Names, Paths ##################

def generate_instance_name(class_name: str):
    """
    Creates a pep8 conform instance name from a pep8 conform class name.
    """

    first, *rest = class_name
    chars = [first.lower()]
    for c in rest:
        if c.isupper():
            chars.extend(['_', c.lower()])
        else:
            chars.append(c)
    return ''.join(chars)


def get_full_name(obj):
    if "__qualname__" in dir(obj):
        name = obj.__qualname__
    else:
        name = obj.__name__
    return obj.__module__ + "." + name


def get_class_members(obj, filter_private=False):
    members = obj.__class__.__dict__.items()
    if filter_private:
        members = ((name, obj) for name, obj in members if not name.startswith("_"))
    return tuple(members)


def args2str(*args, **kwargs):
    """Returns a printable version of psotional and keyword argument list."""

    args = ', '.join(map(str, args))
    kwargs = ', '.join(f"{k}={v}" for k, v in kwargs.items())

    if args and kwargs:
        return args + ', ' + kwargs
    elif args:
        return args
    elif kwargs:
        return kwargs
    else:
        return ''


def pick_valid_keys(callable_, conf):
    """
    Returns the paramters that are valid for a given callable
    Takes all key addressable parameters and ignores the rest.
    """
    # TODO: support **kwargs parameters
    keys = set(inspect.signature(callable_).parameters.keys())
    kwargs = {k:v for k,v  in conf.items() if k in keys}
    return kwargs
    

def escape_path(path):
    """
    Return path relative to local path or replaces home with ~
    """

    path = Path(path)
    local_path = Path('.').absolute()
    if path.is_relative_to(CORE_SERVICE_PATH):
        path = Path("///") / path.relative_to(CORE_SERVICE_PATH)
    if path.is_relative_to(USER_SERVICE_PATH):
        path = Path("//") / path.relative_to(USER_SERVICE_PATH)
    elif path.is_relative_to(local_path):
        path = path.relative_to(local_path)
    elif path.is_relative_to(Path.home()):
       path = Path("~") / path.relative_to(Path.home())
    return path


####################### Alpha-Numeric Coding for Host-IDs ###########################

base_code = string.digits + string.ascii_uppercase + string.ascii_lowercase


def _decompose(number, base):
    """Generate digits from `number` in base alphabet, least significants
    bits first.

    Since A is 1 rather than 0 in base alphabet, we are dealing with
    `number - 1` at each iteration to be able to extract the proper digits.
    """

    while number:
        number, remainder = divmod(number - 1, base)
        yield remainder


def encode_base(number, base):
    """Convert a decimal number to alpha-numeric base representation."""
    return ''.join(base_code[n] for n in _decompose(number, base))[::-1]


def decode_base(code, base):
    """Inverse of encode_base."""
    return sum(base_code.index(c)*(base**i) for i,c in enumerate(code))


def get_host_id():
    """Return the host_id in base62"""
    return encode_base(uuid.getnode(), 62)


############################# Data Structures #################################

class UniqueList(list):
    def __init__(self, iterable):
        """A List that deletes dublicate entries with lower indices"""
        iterable = reversed(dict.fromkeys(reversed(iterable)))
        super().__init__(iterable)

    def append(self, obj):
        if obj in self:
            self.remove(obj)
        super().append(obj)

    def extend(self, iterable):
        for obj in iterable:
            self.append(obj)

    def insert(self, index, obj):
        """Insert object at index and removes dublicate."""
        if obj in self:
            dublicate_index = self.index(obj)
            if dublicate_index < index:
                index -= 1
            self.remove(obj)
        super().insert(index, obj)


class RecordStore:
    def __init__(self, colnames):
        self._records = []
        self.colnames = colnames
        self._dicts = {cn: {} for cn in colnames}

    def add(self, record):
        self._records.append(record)
        for key, col in self._dicts.items():
            val = record.__getitem__(key)
            matching = col.get(val, ())
            new_tuple = (*matching, record)
            col[val] = new_tuple
    
    def get(self, key, value):
        """Return where a """
        return self._dicts[key][value]


############################# Cache Stuff #####################################

def get_cache_folder():
    p = Path("~/.cache/labc/").expanduser()
    p.mkdir(exist_ok=True)
    return p


############################# Subprocesses ####################################


def is_tool(name):
    """
    Check whether `name` is on PATH and marked as executable.
    
    Stolen from: https://stackoverflow.com/questions/11210104/check-if-a-program-exists-from-a-python-script
    """
    # from whichcraft import which
    from shutil import which
    return which(name) is not None
