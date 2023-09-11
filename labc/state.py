import sys
import uuid

from .configuration import load_config
from .server import Server
from .services import (
    ServiceClassRegistry,
    ServiceMethodRegistry, 
    ServiceObjectRegistry,
)
from . import util

# this is the universal-id for the current running instance
uid = str(uuid.uuid1())

# this is necessary to declate the variables for inspection reasons
config = None
server = None
service_class_registry = None
service_method_registry = None

class State(sys.__class__):  # sys.__class__ is <class 'module'>
   
    @property
    def config(self):
        if not hasattr(self, '_config'):
            self._config = load_config()
        return self._config

    @property
    def server(self):
        if not hasattr(self, '_server'):
            kwargs = self.config.get("Server", {})
            kwargs = util.pick_valid_keys(Server, kwargs)
            self._server = Server(**kwargs)
        return self._server

    @property
    def service_class_registry(self) -> ServiceClassRegistry:
        if not hasattr(self, '_service_class_registry'):
            path = self.config["services.paths"]
            self._service_class_registry = ServiceClassRegistry(path)

            # This cannot be in ServiceClassRegistry.__init__
            # otherwise there is an import recursion
            self._service_class_registry.discover_services()

        return self._service_class_registry

    @property
    def service_method_registry(self):
        if not hasattr(self, '_service_method_registry'):
            self._service_method_registry = ServiceMethodRegistry()
        return self._service_method_registry

    @property
    def service_object_registry(self):
        if not hasattr(self, '_service_object_registry'):
            self._service_object_registry = ServiceObjectRegistry()
        return self._service_object_registry

sys.modules[__name__].__class__ = State  # change module class into ´State´
