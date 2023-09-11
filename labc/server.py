import asyncio
from collections import defaultdict
import datetime
from functools import partial
import inspect
import json
import logging
import os
import signal
import socket
import sys
import types
import traceback
from typing import Callable, NamedTuple

from . import state
from . import util

log = logging.getLogger(__name__)


class FunctionRecord(NamedTuple):
    type: str # (sub or reg)
    name: str
    scope: str
    realm: str
    raw: bool
    func: Callable


class Server:

    def __init__(self):

        # do not set this to "localhost" to avoid connecting to "::1" 
        self.host = "127.0.0.1"

        self.router_port = state.config["router"]["port"]
        self.function_table = FunctionTable()
        self._server = None

    async def handle_connection(self, reader, writer):
        try:
            data = await reader.readline()
            message = data.decode()
            addr = writer.get_extra_info('peername')
            log.debug(f"Received message len {len(message)} from {addr!r}")
            #log.debug(f"{data}")

            packet = util.net.loads_json(data)
            msg_type = packet.get("type", None)

            if msg_type == "req":
                result_dict = await self.handle_req(packet)
                result_serialized = json.dumps(result_dict).encode()
                writer.write(result_serialized)

                # this lines sends the result immediately to the caller
                # fixes an issue where a process still ran in the background and the result was not sent
                writer.write_eof()
                await writer.drain()

            elif msg_type == "pub":
                writer.close()
                await self.handle_pub(packet)
                
            elif not packet:
                # this is used to check if server is still up
                # TODO: move this to a dedicated status message
                log.info(f"Empty message from {addr}")

            elif msg_type is None:
                log.error(f"Undefined message type from {addr}")

            else:
                log.error(f"Unknown message type \"{msg_type}\" from {addr}")

        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_req(self, packet):
        name = packet['name']

        if name == "":
            return self.wrap_reply(True)

        if name not in self.function_table.regs:
            return self.wrap_reply("RemoteNameError", type_="err")

        func_rec = self.function_table.regs[name]

        assert len(func_rec) == 1
        func = tuple(func_rec)[0].func
        args, kwargs = util.net.get_arguments(packet)

        if not name.startswith("_"):
            log.info(f"req {name}")
        else:
            log.debug(f"req {name}")
        
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, partial(func, *args, **kwargs))
        except Exception as e:
            log.error(f"{type(e).__name__}({e})")
            log.debug(''.join(traceback.format_stack()))
            return self.wrap_reply("RemoteCallError", "err")

        # test json serializable
        try:
            json.dumps(result)
        except TypeError as e:
            log.error(f"{type(e).__name__}({e})")
            log.debug(''.join(traceback.format_stack()))
            return self.wrap_reply("RemoteEncodingError", "err")

        return self.wrap_reply(result)

    async def handle_pub(self, packet):
        function_records = self.function_table.subs.get(packet['name'])
        log.debug(f"found {len(function_records)} subscriptions for topic {packet['name']}")
        
        args, kwargs = util.net.get_arguments(packet)
        log.debug(f"args: {args}, kwargs: {kwargs}")
        
        for frec in function_records:
            
            is_corot = inspect.iscoroutinefunction(frec.func)

            # Call the function
            if is_corot and frec.raw:
                await frec.func(packet)
            elif is_corot and not frec.raw:
                await frec.func(*args, **kwargs)
            elif not is_corot and frec.raw:
                frec.func(packet)
            elif not is_corot and not frec.raw:
                frec.func(*args, **kwargs)
                
    def add_function_record(self, frec):
        
        self.function_table.add(frec)

        if frec.type == "reg":
            action_name = "register"
        elif frec.type == "sub":
            action_name = "subscribe"
        else:
            raise Exception(f"Unknown function record type: {frec.type}")

        log_msg = "{} {} {}.{} as {}".format(
            action_name,
            type(frec.func).__name__,
            frec.func.__module__,
            frec.func.__qualname__,
            frec.name,
        )
        if frec.name.startswith("_"):
            log.debug(log_msg)
        elif isinstance(frec.func, types.MethodType):
            log.debug(log_msg)
        else:
            log.info(log_msg)

    async def notify_existence(self):
        packet = {
            "type": "router-message",
            "name": "add-server",
            "port": self.port,
            "frecs": self.function_table.get_serializable(),
        }
        await util.aio.send_obj("127.0.0.1", self.router_port, packet)

    async def notify_shutdown(self):
        packet = {
            "type": "router-message",
            "name": "remove-server",
            "port": self.port,
        }
        await util.aio.send_obj("127.0.0.1", self.router_port, packet)

    def is_serving(self):
        if self._server is None:
            return False
        return self._server.is_serving()

    def wrap_reply(self, value, type_="rep"):
        return {
            "type": type_,
            "value": value,
            "host_id": self.host,
            "port": self.port,
            "hostname": socket.gethostname(),
        }

    async def run(self):
        self.port = util.net.find_free_port()
        
        self._server = await asyncio.start_server(
            self.handle_connection, self.host, self.port)
        
        log.info(f'serving on {self.host}:{self.port} in process {os.getpid()}')
        
        self.timestamp = datetime.datetime.utcnow().timestamp()
        
        server_task = asyncio.create_task(self._server.serve_forever())
        
        #server_task.add_done_callback(shutdown())
        asyncio.create_task(self.notify_existence())
        
        try:
            await server_task
        except asyncio.exceptions.CancelledError:
            log.info(f'Server-Task canceld.')
            pass

    async def shutdown(self):
        log.info("Shutting down server.")
        try:
            await self.notify_shutdown()
        except ConnectionRefusedError as cre:
            log.info(f"Failed to notify router of shutdown: {cre}")
        except Exception as e:
            log.error(f"Failed to notify router of shutdown: {e}")
        
        # this is copied from asyncio.Server.__aexit__
        self._server.close()
        await self._server.wait_closed()

    def start(self):
        loop = asyncio.get_event_loop()

        # this part is handling KeyboardInterrups and SIGTERMS from the opperating system
        if sys.platform == "win32":
            signal.signal(signal.SIGINT, lambda code, frame: asyncio.create_task(self.shutdown()))
        else:
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(self.shutdown()))
        
        
        if sys.platform == "win32":
            signal.signal(signal.SIGTERM, lambda code, frame: asyncio.create_task(self.shutdown()))
        else:
            loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(self.shutdown()))

        # this starts the event loop
        loop.run_until_complete(self.run())



class TopicTree:

    topic_seperator = '.'

    def __init__(self):
        self._entries = set()
        self._subtrees = {}

    @classmethod
    def _split(cls, topic):
        """
        Split the topic into its f parts.
        """
        if topic in ('', None):
            return ()
        parts = topic.split(cls.topic_seperator)
        assert '' not in parts, "Empty string cannot be a subtopic. Probability there is a '..' in the topic."
        return tuple(parts)

    def add(self, topic, obj):
        """
        Add an entry.
        """
        if isinstance(topic, str):
            topic = self._split(topic)
        self._add(topic, obj)

    def _add(self, parts, entry):

        if not parts:
            self._entries.add(entry)
        else:
            prefix, *rest = parts
            if prefix not in self._subtrees:
                self._subtrees[prefix] = TopicTree()
            self._subtrees[prefix]._add(rest, entry)

    def get(self, topic):
        """Get all entries for this topic."""
        if (topic is None) or isinstance(topic, str):
            topic_parts = self._split(topic)
        else:
            topic_parts = topic

        return {
            *self._entries,
            *self.iter_parents(topic_parts),
        }

    def iter_parents(self, topic_parts):
        subtree = self
        for part in topic_parts:
            if part not in subtree._subtrees:
                break
            subtree = subtree._subtrees.get(part)
            yield from subtree._entries
    
    def remove(self, topic, obj):
        """
        Removes an entry.
        """

        if not topic:
            self._entries.remove(obj)
            return

        if isinstance(topic, str):
            parts = self._split(topic)
        else:
            parts = topic

        prefix, *rest = parts
        self._subtrees[prefix].remove(rest, obj)
    
    def remove_object(self, obj):
        """
        Removes all entries for an object.
        """

        for subtop in self._subtrees.values():
            subtop.remove_object(obj)

        if obj in self.entries:
            self._entries.remove(obj)

    def remove_topic(self, topic, recursive=False):
        """
        Removes all entries of a topic.
        
       	If recursive also remove all subtopics.

        """

        # DECIDE: remove subtopics if called with empty-topic ?

        if not topic:
            self.entries.clear()
            return

        if isinstance(topic, str):
            topic = topic.split(".")

        prefix, *rest = topic

        #if remove_subtopics and not rest:
        #    del self.subtopics[prefix]

        self._subtrees[prefix].remove_topic(rest, recursive)

    def __iter__(self):
        """
        Iterate all Topics.
        """
        if self._entries:
            yield ''
        for name, subsc in self._subtrees.items():
            yield from (
                name + '.' + topic if topic else name
                for topic in subsc.__iter__()
            )

    def __getitem__(self, topic):
        return self._getitem(self._split(topic))
    
    def _getitem(self, topic_parts):
        if not topic_parts:
            return self._entries
        head, *tail = topic_parts
        return self._subtrees[head]._getitem(tail)
    
    def items(self):
        return [(topic, list(self[topic])) for topic in iter(self)]
    
    """def prepr(self, topic_parts=[]):
        topic = '.'.join(topic_parts)
        lines = [topic]
        for entry in self.entries:
            lines.append(" " * len(topic) + str(entry))
        for key, subtree in self.subtrees.items():
            lines.extend(
                subtree.prepr(".".join([*topic_parts, key]))
            )
        return lines"""
    
    def as_dict(self):
        return {topic: list(self[topic]) for topic in self}


class FunctionTable:

    record_cls = FunctionRecord

    def __init__(self):
        self.subs = TopicTree()
        self.regs = defaultdict(set)
        self.realms = TopicTree()
        self.records = []

    def extend(self, func_recs):
        """Add function records from an iterable."""
        for frec in func_recs:
            self.add(frec)

    def add(self, frec):
        frec = self._ensure_record_class(frec)
        if frec.type == "sub":
            self.subs.add(frec.name, frec)
        elif frec.type == "reg":
            self.regs[frec.name].add(frec)
        self.realms.add(frec.realm, frec)
        self.records.append(frec)
    
    def remove(self, *frecs):
        for frec in frecs:
            frec = self._ensure_record_class(frec)
            print("1.1 ----->", frec)
            if frec.type == "sub":
                print("innen")
                print("subs", [*self.subs.items()])
                self.subs.remove(frec.name, frec)
                print("drauß")
            elif frec.type == "reg":
                self.regs[frec.name].remove(frec)
            self.realms.remove(frec.realm, frec)
            self.records.remove(frec)
    
    @classmethod
    def _ensure_record_class(cls, frec):
        if not isinstance(frec, cls.record_cls):
            return cls.record_cls(*frec)
        else:
            return frec

    def match(self, type, name, scope, realm):
        """
        Return all matching function records.
        """

        #print(type, name, scope, realm)
        #print("records", self.records)
        #print("regs", self.regs)

        if type and (type not in ["sub", "reg"]):
            raise util.ResolutionError(f"Invalide func-type: {type}")

        candidates = set()

        if not type or type == "sub":
            print("x", self.subs.get(name), list(self.subs.items()))
            if name is None:
                items = list(self.subs.items())
                if items:
                    _, values = zip(*items)
                    candidates |= {rec for v in values for rec in v}
            else:
                candidates |= self.subs.get(name)
        
        print("a", candidates)

        if not type or type == "reg":
            if name is None:
                for records in self.regs.values():
                    candidates |= records
            else:
                candidates |= self.regs.get(name, set())

        print("b", candidates)

        if realm:
            candidates &= self.realms.get(realm)

        print("c", candidates)

        if scope:
            candidates = {c for c in candidates if c.scope == scope}
        
        print("d", candidates)

        return candidates

    def get_serializable(self):
        """
        Returns function records as tuples ommiting the actual functions.
        """
        return [r[:-2] for r in self.records]

    def __str__(self):
        return str(self.records)