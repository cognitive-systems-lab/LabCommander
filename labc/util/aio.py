"""
Asyncio versions of utility functions.
"""

import asyncio
import json
from functools import partial

from .net import loads_json, handle_reply


async def to_thread(func, *args, **kwargs):
    """Asynchronously run function *func* in a separate thread.

    Any *args and **kwargs supplied for this function are directly passed
    to *func*. Also, the current :class:`contextvars.Context` is propagated,
    allowing context variables from the main thread to be accessed in the
    separate thread.

    Return a coroutine that can be awaited to get the eventual result of *func*.

    Copied from asyncio module of python 3.9 to be used by older version.
    """
    loop = asyncio.events.get_running_loop()
    # ctx = asyncio.threads.contextvars.copy_context()
    # func_call = functools.partial(ctx.run, func, *args, **kwargs)
    func_call = partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)


# add to_thread to asyncio for python version < 3.9
if "to_thread" not in dir(asyncio):
    asyncio.to_thread = to_thread


async def send_obj(host, port, obj):
    """
    Sends an object to an endpoint asynchroniously.
    """
    port = int(port)
    msg = json.dumps(obj) + "\n"
    data = msg.encode()
    _, writer = await asyncio.open_connection(host, port)
    writer.write(data)
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def send_recv_obj(host, port, obj, *, timeout=None):
    """
    Sends an object to an endpoint and receives a response asynchroniously.
    """
    port = int(port)
    msg = json.dumps(obj) + "\n"
    data = msg.encode()
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(data)
    await writer.drain()
    data = await reader.readline()
    writer.close()
    await writer.wait_closed()
    msg = data.decode()
    obj = loads_json(msg)
    return obj

async def check_up(host, port):
    """
    Sends an empty message to check if server is up and runnning.
    """
    try:
        await send_obj(host, port, {})
    except:
        return False
    else:
        return True

async def request(host, port, name, args=None, kwargs=None):
    """
    Low level implementation of a async remote procedure call.
    """
    packet = {
        "type": "req",
        "name": name,
        "args": args or [],
        "kwargs": kwargs or {},
    }
    return await send_recv_obj(host, port, packet)


async def call(host, port, name, args=None, kwargs=None):
    """
    Encapsulated async request.
    """
    reply = await request(host, port, name, args, kwargs)
    return handle_reply(reply, name)
    

async def publish(host, port, name, args=None, kwargs=None):
    """
    Low level implementation message publishing.
    """
    packet = {
        "type": "pub",
        "name": name,
        "args": args or [],
        "kwargs": kwargs or {},
    }
    await send_obj(host, port, packet)
