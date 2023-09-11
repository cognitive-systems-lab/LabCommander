import copy
import functools
import inspect
import logging
import time

from . import util
from . import state
from .server import FunctionRecord
from .router import is_router_running, start_local_router

log = logging.getLogger(__name__)


def register(arg=None, *, name=None, scope="network", realm="", raw=False):
    """
    Register a callable object as a remote-procedure.
    """
    # if func is None assume that register was called in a decorator
    if arg is None:
        return functools.partial(register, name=name, scope=scope)

    if name is None:
        name = arg.__name__

    # figures out if register was used as a decorator
    lines = inspect.stack(context=2)[1].code_context
    decorated = any(line.strip().startswith('@') for line in lines)

    func = arg
    func_rec = FunctionRecord('reg', name, scope, realm, raw, func)
    if decorated:
        state.service_method_registry.register(func_rec)
    else:
        state.server.add_function_record(func_rec)
    
    if decorated:
        return arg


def register_service(service_class=None, *, name=None):
    """
    Register a class as a service.
    """
    
    # if func is None assume that register was called in a decorator
    if service_class is None:
        return functools.partial(register_service, name=name)
    
    assert inspect.isclass(service_class),\
        "Only a class can be registered as a serivice."

    if name is None:
        name = service_class.__name__

    # figures out if register was used as a decorator
    lines = inspect.stack(context=2)[1].code_context
    decorated = any(line.strip().startswith('@') for line in lines)

    state.service_class_registry._register(name, service_class)

    if decorated:
        return service_class



def subscribe(func=None, *, topic=None, scope="network", realm=None, raw=False):
    """
    Subscribe a function to a topic.
    """

    # if func is None assume that register was called in a decorater
    if func is None:
        return functools.partial(subscribe, topic=topic, scope=scope)

    if topic is None:
        topic = func.__name__

    if realm is None:
        realm = state.config["general"]["realm"]

    # figure out if register was used as a decorator
    lines = inspect.stack(context=2)[1].code_context
    decorated = any(line.strip().startswith('@') for line in lines)     

    func_rec = FunctionRecord('sub', topic, scope, realm, raw, func)

    if decorated:
        state.service_method_registry.register(func_rec)
        return func

    state.server.add_function_record(func_rec)


def watch(func=None, *, topic=None, on_return=False, scope="network"):
    """
    Publish to a topic when function is called.

    Use this as a dector for a function:
    """

    # if func is None assume that register was called in a decorater
    # Todo: this breaks the functools.wraps
    if func is None:
        return functools.partial(watch, topic=topic, on_return=on_return, scope=scope)

    @functools.wraps(func)
    def watch_wrapper(*args, **kwargs):
        if not on_return:
            publish(topic, scope=scope)
        
        result =  func(*args, **kwargs)
        
        if on_return:
            publish(topic, scope=scope)
        
        return result

    return watch_wrapper


def serve(host=None, port=None):
    """
    Start a new function server.
    """

    #if start_services:
    #    autostart_services = map(str.strip, self.config.service.autostart.split(','))
    #    for service_name in autostart_services:
    #        if not self.is_service_loaded(service_name):
    #            self.load(service_name)

    #if not self.discovery.is_running():
    #    self.discovery.start()

    if not is_router_running():
        start_local_router()
        # wait for the router to start
        while not is_router_running(): 
            time.sleep(0.1)

    import setproctitle
    import sys
    title = ' '.join(["labc", *sys.argv[1:]])
    setproctitle.setproctitle(title)

    try:
        state.server.start()
    except KeyboardInterrupt:
        # print() # so the following log.info gets a new line after ^C -> does not work if other thread print logs
        log.info("Closed by user with Ctrl+C")


def load(service, route_name: str = None, args=None, kwargs=None) -> None:
    """
    Loads a service into the server.
    """

    is_str = isinstance(service, str)
    is_type = isinstance(service, type)

    if is_str:
        # service_name = state.service_class_registry.get_full_name(service)
        service_class = state.service_class_registry[service]

    if is_type:
        service_class = service

    if not (is_str or is_type):
        service_class = type(service)
        service_obj = service
    else:
        service_obj = None

    # service_name = util.get_full_name(service_class)
    service_name = service_class.__name__


    if route_name is None:
        route_name = util.generate_instance_name(service_name)
    

    # prepere args and kwargs
    if service_obj is None:

        args = () if args is None else args

        if service_name in state.config:
            conf_kwargs = dict(state.config[service_name])
        else:
            conf_kwargs = {}

        kwargs = {} if kwargs is None else kwargs
        new_kwargs = copy.copy(conf_kwargs)
        new_kwargs.update(kwargs)
        kwargs = new_kwargs
    else:
        if args or kwargs:
            log.error("Loading a service by object does not make use of arguments!")

    # create object
    if service_obj is None:
        kwargs = util.pick_valid_keys(service_class, kwargs)
        service_obj = service_class(*args, **kwargs)

    state.service_object_registry.load(service_obj, route_name)

def is_service_loaded(self, name_or_cls):
    """Checks whether a services is current loaded into the labc instance."""
    if isinstance(name_or_cls, str):
        name = name_or_cls
        full_service_name = labc.service.ServiceCollection.get_full_class_name(name)
        route_name = labc.utils.generate_instance_name(name)
        loaded = (route_name in self.list_loaded_services())
    elif isinstance(name_or_cls, type):
        cls_ = name_or_cls
        loaded_classes = (type(service) for service in self.services.loaded.values())
        loaded = (cls_ in loaded_classes)
    else:
        obj = name_or_cls
        loaded = (obj in self.services.loaded.values())
    return loaded


def unload(service_route):
    """
    Unload a service.
    """
    raise NotImplementedError()


def list_loaded_services(self):
    """Returns a list of local services."""
    return tuple(self.services.loaded.keys())


def list_available_services():
    return [
        (name, cls.__module__ + "." + cls.__name__, inspect.getmodule(cls).__file__)
        for name, cls in state.service_class_registry.items()
    ]


"""
def list_available_services():
    return tuple(state.service_class_registry.keys())
"""

def list_remote_functions(self):
    """Returns a list of local services."""
    self.init_discovery(wait=True)
    return tuple(self.client.remote_function_records.values())


def init_discovery(self, *, wait=False):
    """Start discovery server."""
    if not self.discovery.is_running():
        self.discovery.start()
        if wait:  # wait for all the function records to arrive
            t = float(wait)
            time.sleep(t)


def call(name: str, args=None, kwargs=None, *, scope="network", realm=None, host=None, port=None):
    """
    Calls a remote function and returns the return value of the function.
    """
    
    packet = {
        "type": "req",
        "name": name,
        "args": args,
        "kwargs": kwargs,
        "host_id": host,
        "port": port,
        "scope": scope,
        "realm": realm,
    }
    router_port = state.config["router"]["port"]
    reply = util.net.send_recv_obj("127.0.0.1", router_port, packet)
    return util.net.handle_reply(reply, name)


def publish(topic: str, args=None, kwargs=None, *, scope="network", host=None, port=None):   
    """
    Publish messages to a topic.
    """
    packet = {
        "type": "pub",
        "name": topic,
        "args": args,
        "kwargs": kwargs,
        "host_id": host,
        "port": port,
        "scope": scope,
    }
    router_port = state.config["router"]["port"]
    util.net.send_obj("localhost", router_port, packet)


def get_namespace(route=None, scope="network", realm=None, host=None, port=None):
    """Create a namespace for the current labc-instance."""
    return Namespace(route, scope, realm, host, port)


def forward_logging(self, topic="log", level=0):
    """
    Forward logging to the Message Queue.
    """
    self.init_discovery(wait=True)
    handler = PublishHandler(self, topic, level)
    #filter_ = RecursionFilter()
    #handler.addFilter(filter_)
    #formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    #handler.setFormatter(formatter)
    logging.root.addHandler(handler)


class Namespace:
    """
    Highlevel interface for calling and publishing.
    """
    def __init__(self, route=None, scope=None, realm=None, host=None, port=None):
        self._route = route
        self._scope = scope
        self._realm = realm
        self._host = host
        self._port = port

    def __getattr__(self, attr):
        if self._route is None:
            route = attr
        else:
            route = self._route + '.' + attr
        return Namespace(route, self._scope, self._realm, self._host, self._port)
        # return self.__getattribute__(attr)

    def __str__(self):
        return f"{self.__class__.__name__}({self._route}, {self._scope}, {self._realm}, {self._host}, {self._port})"

    def __repr__(self):
        return str(self)

    def __call__(self, *args, **kwargs):
        """
        Execute the actions for the current route.
        """
        return call(
            self._route, args, kwargs,
            scope=self._scope,
            host=self._host,
            port=self._port,
        )

    def __lshift__(self, arg):
        """
        A left shift operator ( << ) can be used as an alias for publishing to a topic.

        arg -- Arguments to be published, Either tuple for position or dict for keyword arguemtns.
        """

        if isinstance(arg, tuple):
            args = arg
            kwargs = {}
        elif isinstance(arg, dict):
            args = ()
            kwargs = arg
        else:
            primitive = (int, float, bool, str, type(None))
            if isinstance(arg, primitive):
                args = (arg,)
                kwargs = {}
            else:
                raise ValueError("Argument for lshift operator must be tuple, dict or of primitive type.")

        publish(
            self._route, args, kwargs,
            scope=self._scope,
            host=self._host,
            port=self._port,)


    # dunder-methods that get forwarded
    # this might be solved with a __getattribute__  and/or meta-class approach

    def __iter__(self, item):
        return self._state.call(
            name=self._route + '.__getitem__',
            args=(item,),
            kwargs={},
            scope=self._scope,
        )

    def __len__(self):
        return self._state.call(
            name=self._route + '.__len__',
            args=(),
            kwargs={},
            scope=self._scope,
        )

    def __contains__(self, item):
        return self._state.call(
            name=self._route + '.__contains__',
            args=(item,),
            kwargs={},
            scope=self._scope,
        )

    def __index__(self, item):
        return self._state.call(
            name=self._route + '.__index__',
            args=(item,),
            kwargs={},
            scope=self._scope,
        )

    def __getitem__(self, item):
        return self._state.call(
            name=self._route + '.__getitem__',
            args=(item,),
            kwargs={},
            scope=self._scope,
        )

    def __setitem__(self, key, value):
        return self._state.call(
            name=self._route + '.__setitem__',
            args=(key, value),
            kwargs={},
            scope=self._scope,
        )


class PublishHandler(logging.Handler):
    def __init__(self, labc_instance, topic="log", level=0):
        super().__init__(level)
        self.labc_instance = labc_instance
        self.topic = topic


    def emit(self, record):

        # Avoid the labc.publish method because it introduces recursion !
        # self.labc_instance.publish(self.topic, record.__dict__)

        log_msg = self.format(record)

        # TODO: make this more sophisticated
        for ip_addr, port, hostname in self.labc_instance.remotes.get_endpoints():
            try:
                util.publish(ip_addr, port, self.topic, (log_msg,))
            except ConnectionRefusedError:
                # something is a receiving server here !
                # TODO: This should probablty start a reevalution of the server addresses !
                pass
            #print(ip_addr, port, self.topic)


"""class RecursionFilter:
def filter(self, record):
    print(record.__dict__)
    return False"""

__all__ = [
    "register", "serve", "subscribe", "watch", "call", "publish",
    "register_service", "load", "list_available_services", "get_namespace"]