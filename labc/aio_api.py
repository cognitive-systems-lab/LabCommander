import logging

from . import aio_util
from .. import state


log = logging.getLogger(__name__)


async def call(name: str, args=None, kwargs=None, *, scope="network", host=None, port=None):
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
    }
    router_port = state.config["router"]["port"]
    result = await aio_util.send_recv_obj("localhost", router_port, packet)
    return result


async def router_request(name, **kwargs):
    """
    Calls a remote function and returns the return value of the function.
    """
    
    packet = {
        "type": "router-request",
        "name": name,
        **kwargs,
    }
    router_port = state.config["router"]["port"]
    result = await aio_util.send_recv_obj("127.0.0.1", router_port, packet)
    return result
