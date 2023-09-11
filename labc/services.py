# from inspect import isclass as is_class

from pathlib import Path
import logging
import pkgutil
from importlib.machinery import SourceFileLoader

import appdirs

from . import state
from . import util
from .server import FunctionRecord


log = logging.Logger(__name__)

CORE_SERVICE_PATH = Path(__file__).parent / "services"
USER_SERVICE_PATH = Path(appdirs.user_data_dir("labc")) / "services"


class ServiceClassRegistry(dict):
    def __init__(self, paths):
        super().__init__()
        self.paths = paths
    
    def __getitem__(self, key):
        """
        Call :py:meth:`get` with empty args and kwargs from config.
        """

        # TODO: should this even be here or in api.register ?
        kwargs  = state.config.get(key ,{})
        return self.get(key, **kwargs)
    
    def discover_services(self):
        """
        Discovers serives by importing all modules from the services folder.
        """
        dicovered_modules = self.discover_service_modules()
        return self.import_modules_from_infos(dicovered_modules)

    def discover_service_modules(self):
        """
        Discover all importable modules in the service path.
        """
        local_paths = (
            Path(path).expanduser()
            for path in self.paths
        )
        paths = (
            *local_paths,
            USER_SERVICE_PATH,
            CORE_SERVICE_PATH,
        )
        paths = map(str, paths)
        return pkgutil.iter_modules(paths)

    @staticmethod
    def import_modules_from_infos(module_infos):
        """
        Load all modules from a list of module infos.
        """

        # TODO: load_module is deprecated: find solution with exec_module    
        # TODO: extend to bytecode files (.pyc)

        loaded_modules = {}
        for finder, module_name, is_pkg in module_infos:
            
            if is_pkg:
                module_path = Path(finder.path) / module_name / "__init__.py"
            else:
                module_path = (Path(finder.path) / module_name).with_suffix(".py")

            try:
                module = SourceFileLoader(module_name, str(module_path)).load_module()
            except Exception as err:
                log.error(f"Could not import module: {module_path} - {err}")
            else:
                loaded_modules[module_name] = module

        return loaded_modules
    
    def _register(self, key: str, class_: type) -> None:
        """
        Registers a class with the registry.

        :param key: Has already been processed by :py:meth:`gen_lookup_key`.
        """
        if not isinstance(key, str) or key == "":
            raise ValueError(
                'Attempting to register class {cls} '
                'with invalid registry key {key!r}.'.format(
                    cls=class_.__name__,
                    key=key,
                ),
            )
        
        if key in self and self[key] != class_:
            err = ValueError(
                '{cls} with key {key!r} is already registered.'.format(
                    cls=class_.__name__,
                    key=key,
                ),
            )
            log.error(repr(err))
            return

        self.__setitem__(key, class_)

    def get_full_name(self, name):
        """
        Returns the full service class name.
        """
        parts = name.split('.')
        print(parts)
        f = lambda sn: sn.split('.')[-len(parts):] == parts
        resolved = tuple(filter(f, self.keys()))
        assert len(resolved) == 1
        return resolved[0]


class ServiceMethodRegistry(dict):
    def register(self, func_rec):
        self.__setitem__(func_rec.func, func_rec)


class ServiceObjectRegistry(dict):

    def load(self, obj, route_name):
        """
        Loads an object as a service.
        """

        assert route_name not in self, \
            f"Service already loaded with route name \"{route_name}\""
        
        log.info(f"Load {obj} as {route_name}.")
        self[route_name] = obj

        for func_name, cls_func in util.get_class_members(obj):

            if not callable(cls_func):
                continue

            if cls_func not in state.service_method_registry:
                continue

            cls_frec = state.service_method_registry[cls_func]
            obj_frec = cls_frec._asdict()
            obj_frec.update({
                "func": obj.__getattribute__(func_name),
                "name": route_name + '.' + cls_frec.name,
            })
            obj_frec = FunctionRecord(**obj_frec)            
            state.server.add_function_record(obj_frec)
