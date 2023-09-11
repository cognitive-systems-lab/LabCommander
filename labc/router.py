import asyncio
from copy import copy
import datetime
import errno
import json
import logging
import traceback
import ipaddress
from pathlib import Path
import random
import signal
import socket
import sys
import time

import paramiko
import appdirs

from . import util
from . import state
from .server import FunctionTable
from .util.net import RemoteFunctionRecord


log = logging.getLogger(__name__)
loglevel = state.config["router.loglevel"] or state.config["general.loglevel"]
log.setLevel(loglevel.upper())
#log.getChild("discover").setLevel("DEBUG")


def is_router_running():
    """
    Returns weather the router is running on the dedicated port.
    """
    try:
        result = router_request("running")
        result = result["value"]
    except ConnectionRefusedError:
        result = False
    return result

def get_router_functions():
    ...


def single_ssh_call(cmd, host):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.connect(host)
    stdin, stdout, stderr = client.exec_command(" ".join(cmd))
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    client.close()
    return out, err


def get_platform(host):
    cmd = ['python3', '-c', '"import sys; print(sys.platform)"']
    return single_ssh_call(cmd, host)


def start_remote_router(host, *args):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.connect(host)
    cmd = ["python3", "-m", "labc", "--daemon", *map(str, args)]
    stdin, stdout, stderr = client.exec_command(" ".join(cmd))
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err


def setup_ssh():
    """Creates RSA key and Copies identity to host."""

    private_key, public_key = paramiko.generate_key_pair(key_type='rsa', key_size=2048)

    path = Path(appdirs.user_data_dir()) / "labc"

    # Save the private key to a file
    with open(path / 'private_key.pem', 'w') as f:
        f.write(private_key.export_key().decode())

    # Save the public key to a file
    with open(path / 'public_key.pub', 'w') as f:
        f.write(public_key.export_key().decode())

    ...


def start_remote_router_2(host):
    """
    Start router on remote host in dedicated environment.

    python -c "import platform; print(platform.system())"
    mkdir -p ~/.local/share/labc/router
    cd ~/.local/share/labc/router
    pipenv install labc
    pipenv shell
    labc router --daemon
    """
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.connect(host)

    cmd = ["python3", "-m", "labc", "--daemon", *map(str, args)]
    stdin, stdout, stderr = client.exec_command(" ".join(cmd))
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err


def start_local_router(args=(), standalone=True):
    """
    Start a router.
    """
    #import sys
    #exec_path = sys.argv[0]
    import subprocess as sp
    python_exec = "/usr/bin/env", "python3"
    cmd = [*python_exec, "-m", "labc", "route", "--daemon", *map(str, args)]
    sp.run(cmd)


def is_router_running(host=None, port=None):
    try:
        router_request("running")
    except ConnectionRefusedError as error:
        return False
    else:
        return True


def router_request(name: str, **kwargs):
    """
    Calls a remote function and returns the return value of the function.
    """

    packet = {
        "type": "router-request",
        "name": name,
        **kwargs,
    }
    router_port = state.config["router"]["port"]
    reply = util.net.send_recv_obj("localhost", router_port, packet)
    return reply


def router_call(name:str, **kwargs):
    reply = router_request(name, **kwargs)
    result = util.net.handle_reply(reply, name)
    if name in ("function-table", "routing-table"):
        result = [util.net.RemoteFunctionRecord(*r) for r in result]
    return result


def router_message(name, router_host=None, router_port=None, **kwargs):
    """
    Send message to a router.
    """
    router_host = router_host or "localhost"
    router_port = state.config["router"]["port"]

    packet = {
        "type": "router-message",
        "name": name,
        **kwargs,
    }

    result = util.net.send_obj(router_host, router_port, packet)
    return result


class Router:

    MAX_DISCOVERY_CONNECTIONS = 255
    DISCOVERY_TIMEOUT = 5 # seconds

    def __init__(self, host, port, known_peers, discover_from_subnets, discover_from_hostsfile, discover_from_tailscale, **kwargs):
        self.host_id = util.get_host_id()
        self.hostname = socket.gethostname()
        self.host = host
        self.port = port
        self.known_peers = known_peers
        self.discover_from_subnets = discover_from_subnets
        self.discover_from_hostsfile = discover_from_hostsfile
        self.discover_from_tailscale = discover_from_tailscale
        self.routing_table = RoutingTable()
        self.local_functions = []
        self.local_servers = []
        self.remote_routers = RemoteRouters()
        self.uptime = None

    async def handle_connection(self, reader, writer):
        try:
            data = await reader.readline()
            #message = data.decode()
            addr = writer.get_extra_info('peername')

            msg_dict = util.net.loads_json(data)
            msg_type = msg_dict.get("type", None)

            if msg_type == "req":
                result_dict = await self.handle_request(msg_dict)
                result_serialized = json.dumps(result_dict).encode()
                writer.write(result_serialized)

                # this lines sends the result immediately to the caller
                # fixes an issue where a process still ran in the background and the result was not sent
                writer.write_eof()
                await writer.drain()

            elif msg_type == "pub":
                #writer.close()
                await self.handle_publish(msg_dict)

            elif msg_type == "sync":
                await self.handle_sync(msg_dict, reader, writer)

            elif msg_type == "router-message":
                try:
                    # asyncio.create_task(
                    await self.handle_router_message(msg_dict, addr)
                except Exception as err:
                    log.error(f"Error while handling router message: {type(err).__name__}({err}).")
                    log.info(msg_dict)

            elif msg_type == "router-request":
                result_dict = await self.handle_router_request(addr, msg_dict)
                result_serialized = json.dumps(result_dict).encode()
                writer.write(result_serialized)
                writer.write_eof()
                await writer.drain()

            elif not msg_dict:
                log.error("Empty run request.")

            elif msg_type is None:
                log.error("Message type not defined!")

            else:
                log.error(f"Unknown message type: {msg_type}")
                print(msg_dict)

        finally:
            writer.close()

    async def handle_request(self, packet):
        """In routers requests are forwarded."""

        candidates = self.routing_table.match(
            name=packet["name"],
            host_id=packet.get("host_id", None),
            port=packet.get("port", None),
            scope=packet.get("scope", None),
            realm=packet.get("realm", None),
            type="reg",
        )

        if candidates:
            frec = random.choice(list(candidates))
            if frec.host_id == self.host_id:
                ip_addr = "127.0.0.1"
                port = frec.port
            else:
                ip_addr = self.remote_routers.choose_ip(frec.host_id)
                packet = copy(packet) # avoid potential side-effects
                packet["host_id"] = frec.host_id
                packet["port"] = frec.port
                port = self.port

            reply = await util.aio.send_recv_obj(ip_addr, port, packet)
        else:
           reply = {
                "type": "err",
                "value": "RemoteNameError",
            }
        return reply

    async def handle_reply(self, msg_dict):
        raise NotImplementedError()

    async def handle_publish(self, packet):
        function_records = self.routing_table.match(
            name=packet["name"],
            host_id=packet.get("host_id", None),
            port=packet.get("port", None),
            scope=packet.get("scope", None),
            realm=packet.get("realm", None),
            type="sub",
        )

        local_ports = set()
        remote_destinations = set()
        for frec in function_records:
            if frec.host_id == self.host_id:
                local_ports.add(frec.port)
            else:
                remote_destinations.add(frec.host_id)

        for port in local_ports:
            ip_addr = "127.0.0.1"
            asyncio.create_task(util.aio.send_obj(ip_addr, port, packet))

        for remote_host_id in remote_destinations:
            # here I have to change the host_id of the packet so it does not
            # get send back. The packet needs to be copied because they are shared
            # among mutliple tasks
            new_packet = copy(packet)
            new_packet["host_id"] = remote_host_id
            ip_addr = self.remote_routers.choose_ip(remote_host_id)
            asyncio.create_task(util.aio.send_obj(ip_addr, self.port, new_packet))

    """
    def hrm_get_router_messages(self):
        methods = (name for name, member in inspect.getmembers(self) if inspect.ismethod(member))
        router_message_handlers = (name[4:].replace('_', '-') for name in methods if name.startswith("hrm_"))
        return tuple(router_message_handlers)
    """


    """ Attempt for a future replacement ...
    async def handle_router_message(self, packet, addr):

        # ...

        log.info(f"Recive router message {packet['name']} from {addr}.")

        if packet['name'] in self.hrm_get_router_messages():
            log.error(f"Unknown router message {packet['name']}.")

        method_name = "hrm_" + packet["name"].replace("-", "_")
        method = self.__dict__[method_name]


        method(packet)
    """


    async def handle_router_message(self, packet, addr):

        log.info(f"Recive router message {packet['name']} from {addr}.")

        if packet["name"] == "add-server":
            await self.handle_add_server(packet)

        elif packet["name"] == "remove-server":
            await self.handle_remove_server(packet)

        elif packet["name"] == "remove-router":
            host_id = packet['host_id']
            hostname = self.remote_routers.get_hostname(host_id)
            log.info(f"Remove router {hostname}")
            self.remote_routers.remove(host_id)
            self.routing_table.remove_match(host_id=host_id)

        elif packet["name"] == "update-routing-table":
            #print("1 ---->", self.routing_table)
            self.routing_table.remove(*packet["frecs-remove"])
            #print("2 ---->", packet["frecs-add"])
            self.routing_table.extend(packet["frecs-add"])

        elif packet["name"] == "update-server-list":
            await self.update_server_list()

        elif packet["name"] == "shutdown":
            await self.shutdown()

        else:
            log.error(f"Unknown router message {packet['name']}.")

    async def handle_add_server(self, packet):
        """
        Adds a new local server to the server-list.
        """
        port = packet["port"]
        log.info(f"Add local server at port {port}.")
        self.local_servers.append(port)
        frecs = [
            RemoteFunctionRecord(*r, self.host_id, port)
            for r in packet["frecs"]
        ]
        #self.routing_table.extend(frecs)
        self.local_functions.extend(frecs)

        #print("Topics:", *self.routing_table.subs)
        #print("Get topics:", self.routing_table.subs.get(""))
        #print("Subtrees:", self.routing_table.subs._subtrees)
        #print("Items:", self.routing_table.subs.items())

        # Tell peers that there is a new server
        packet = {
            "type": "router-message",
            "name": "update-routing-table",
            "frecs-add": frecs,
            "frecs-remove": []}

        await self.router_broadcast(packet)

    async def handle_remove_server(self, packet):
        """
        Removes a local server to the server-list.
        """
        port = packet["port"]
        log.info(f"Remove local server at port {port}.")
        self.local_servers.remove(port)
        frecs = self.routing_table.match(host_id=self.host_id, port=port)
        
        # this is currently handeled by the router broadcast (however there is an argument to not broadcast is to the same server itself)
        #for rec in frecs:
        #    self.routing_table.remove(rec)
        
        packet = {
            "type": "router-message",
            "name": "update-routing-table",
            "frecs-add": [],
            "frecs-remove": list(frecs)}
        await self.router_broadcast(packet)

    async def update_server_list(self):
        """
        Checks if local servers are still running and ungesters the ones who are down.
        """
        for port in self.local_servers:
            is_up = await util.aio.check_up("localhost", port)
            print("...", port, is_up)
            if is_up:
                continue
            await self.handle_remove_server({
                "type": "router-message",
                "name": "remove-server",
                "port": self.port,
            })    

    async def handle_router_request(self, addr, packet):
        log.info(f"Recive router request {packet['name']} from {addr}.")
        if packet["name"] == "routing-table":
            out_packet = {
                "type": "rep",
                "value": self.routing_table.records,
            }
        elif packet["name"] == "topic-tree":
            print(self.routing_table.subs.items())
            out_packet = {
                "type": "rep",
                "value": self.routing_table.subs.as_dict(),
            }
        elif packet["name"] == "function-table":
            out_packet = {
                "type": "rep",
                "value": self.local_functions,
            }
        elif packet["name"] == "remote-routers":
            out_packet = {
                "type": "rep",
                "value": self.remote_routers,
            }
        elif packet["name"] == "running":
            out_packet = {
                "type": "rep",
                "value": True,
            }
        elif packet["name"] == "handshake":
            out_packet = self.handle_handshake(addr, packet)
        elif packet["name"] == "hostname":
            host_id = packet["host_id"]
            if host_id == self.host_id:
                hostname = self.hostname
            else:
                hostname = self.remote_routers[host_id]
            out_packet = {
                "type": "rep",
                "value": hostname,
            }    
        else:
            log.error(f"Unknown router request: {packet['name']}")
            return {
                "type": "err",
                "value": None}
        return out_packet

    async def router_broadcast(self, packet):
        """
        Send packet to all Routers.
        """
        # packet = {k:v for k,v in packet.items()} # shallow copy

        tasks = []
        for host_id in self.remote_routers.keys():
            ip = self.remote_routers.choose_ip(host_id)
            task = asyncio.create_task(util.aio.send_recv_obj(ip, self.port, packet))
            # task.set_exception_handler(lambda loop, context: print(context))
            tasks.append(task)
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def initiate_handshake(self, addr):
        packet = {
            "type": "router-request",
            "name": "handshake",
            "host_id": self.host_id,
            "hostname": self.hostname,
            "port": self.port,
            "frecs": self.local_functions,
        }
        corot = util.aio.send_recv_obj(addr, self.port, packet)
        packet = await asyncio.wait_for(corot, timeout=self.DISCOVERY_TIMEOUT)
        log.info(f"Handshake with {packet['hostname']} ({addr}).")
        self.remote_routers.add(packet["host_id"], packet["hostname"], packet["port"], addr)
        self.routing_table.extend(packet["frecs"])

    def handle_handshake(self, addr, packet):
        ip, port = addr
        log.info(f"Handshake with {packet['hostname']} ({ip}).")
        self.remote_routers.add(packet["host_id"], packet["hostname"], packet["port"], ip)
        self.routing_table.extend(packet["frecs"])
        packet = {
            "type": "router-reply",
            "name": "handshake",
            "host_id": self.host_id,
            "hostname": self.hostname,
            "port": self.port,
            "frecs": self.local_functions,
        }
        return packet

    async def discover(self):
        """
        Discover other routers.
        """

        dislog = log.getChild("discover")
        tic = time.monotonic()

        if not self.discover_from_subnets:
            dislog.info("Discovering peers from subnets is turned off.")

        address_queue = asyncio.Queue()
        for addr, port in self.get_discovery_addresses():
            # TODO: actually include non-default ports
            address_queue.put_nowait(addr)

        tasks = []
        for _ in range(self.MAX_DISCOVERY_CONNECTIONS):
            task = asyncio.create_task(self._discovery_worker(address_queue))
            tasks.append(task)

        await address_queue.join()

        # Cancel our worker tasks.
        for task in tasks:
            task.cancel()

        # Wait until all worker tasks are cancelled.
        await asyncio.gather(*tasks, return_exceptions=True)

        toc = time.monotonic() - tic

        dislog.info(f"Discovery took {toc:.2f} seconds.")


    async def _discovery_worker(self, address_queue):
        dislog = log.getChild("discover")
        while True:
            addr = await address_queue.get()

            tic = time.monotonic()

            try:
                try:
                    await self.initiate_handshake(addr)
                finally:
                    toc = time.monotonic() - tic

            except OSError as e:
                if e.errno == errno.EHOSTUNREACH:
                    dislog.debug(f"Host unreachable {addr} ({toc:.2f} secs)")
                elif e.errno == errno.ECONNREFUSED:
                    dislog.debug(f"Connection refused {addr} ({toc:.2f} secs)")
                elif e.errno == errno.ETIMEDOUT:
                    # appears when trying certain tailscale addresses
                    dislog.debug(f"{e} ({toc:.2f} secs)")
                elif e.errno == errno.ENETUNREACH:
                    dislog.debug(f"")
                else:
                    print("------------------->", e.errno)
                    dislog.warn(f"While processing {addr} - {type(e).__name__}[{e.errno}] - {e} ({toc:.2f} secs)")
            except asyncio.TimeoutError as e:
                dislog.debug(f"Connection Timeout {addr} ({toc:.2f} secs)")
            except Exception as e:
                dislog.error(f"While processing {addr} - {type(e).__name__} - {e} ({toc:.2f} secs)")
                dislog.debug(''.join(traceback.format_stack())) # also print stack trace
            else:
                dislog.info(f"Discovered {addr} ({toc:.2f} secs)")
            finally:
                address_queue.task_done()


    def get_discovery_addresses(self):
        """
        Generate a list of ip-addresses for discovery.
        """

        """
        # snipped to use systems' routing table to get more subnets
        if from_route:
            try:
                route_subnets = util.net.get_subnets_from_route()
            except FileNotFoundError() as fnf_err:
                log.warn("Cannot get subnets from route.")
            else:
                subnets.extend(route_subnets)
        """

        own_addrs = util.net.get_inet_addrs()

        addrs = []

        # first add known peers
        for addr_range in self.known_peers:
            ip, block, port = util.net.parse_address_range(addr_range, default_port=self.port)
            for ip_addr in ipaddress.ip_interface(ip + "/" + block).network:
                addrs.append((ip_addr.exploded, port))

        # second add hostfile hosts
        if self.discover_from_hostsfile:
            try:
                hf_inet_addrs = util.net.get_peers_from_hostsfile()
            except FileNotFoundError as e:
                log.warn("Hostsfile not found.")
            for ip_addr in hf_inet_addrs:
                addrs.append((ip_addr.exploded, self.port))

        # third add tailscale addresses
        if self.discover_from_tailscale:
            if not util.is_tool("tailscale"):
                log.warn("Could not find tailscale. Maybe not installed or not in path?")
            else:
                try:
                    ts_inet_addrs = util.net.get_peers_from_tailnet()
                except Exception as e:
                    log.error("Tailscale found but execution failed.")
                else:
                    for ip_addr in ts_inet_addrs:
                        addrs.append((ip_addr.exploded, self.port))

        # third add addressses from network interface subnets
        if self.discover_from_subnets:

            subnets = {
                ipaddress.ip_interface(ip_addr.exploded + "/24").network
                for ip_addr in own_addrs
            }

            for subnet in subnets:
                for ip_addr in subnet:
                    addrs.append((ip_addr.exploded, self.port))


        # remove mutlicast, loopback and broadcast addresses
        addrs = [(ad, port) for ad, port in addrs if util.net.is_valid_host_address(ad)]

        # remove dublicate addresses while preserving the order
        addrs = [ad for n, ad in enumerate(addrs) if ad not in addrs[:n]]

        # remove own addresses
        addrs = [ad for ad in addrs if ad not in own_addrs]

        return addrs

    async def run(self):

        self._server = await asyncio.start_server(
            self.handle_connection, self.host, self.port)

        log.info(f'Router started on {self.host}:{self.port}.')

        self.timestamp = datetime.datetime.utcnow().timestamp()

        server_task = asyncio.create_task(self._server.serve_forever())

        asyncio.create_task(self.discover())

        try:
            await server_task
        except asyncio.exceptions.CancelledError:
            log.debug(f'Router-Task canceld.')
            pass

        # TODO: so maybe to handle this it is best to put this in a task and cancel it properly
        # async with self._server:
        #    await self._server.serve_forever()

    #def start(self):
    #    loop = asyncio.get_event_loop()
    #    try:
    #        loop.run_until_complete(self.run())
    #    except KeyboardInterrupt as be: # also catches KeyboardInterrupts
    #        # TODO: gracefully handle KeyboardInterrupts
    #        raise be

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

        if is_router_running():
            log.error(f"Router already running on port {self.port}")
        else:
            loop.run_until_complete(self.run())


    async def shutdown(self, signal=None):
        log.info("Shutting down router...")
        packet = {
            "type" : "router-message",
            "name" : "remove-router",
            "host_id": self.host_id,
        }
        try:
            await self.router_broadcast(packet)
        except Exception as e:
            log.error(f"Could not broadcost router termination: {e}")

        # this is copied from asyncio.Server.__aexit__
        self._server.close()
        await self._server.wait_closed()


class RoutingTable(FunctionTable):

    record_cls = RemoteFunctionRecord

    def remove_match(self, *, type=None, name=None, scope=None, realm=None, host_id=None, port=None):
        """
        Removes all function records matching the input args.
        """
        print("call remove_match")
        for frec in self.match(type, name, scope, realm, host_id, port):
            print(frec)
            self.remove(frec)

    def match(self, type=None, name=None, scope=None, realm=None, host_id=None, port=None):
        """
        Return all matching function records.
        """
        candidates = super().match(type, name, scope, realm)
        print(1, candidates)

        if host_id:
            candidates = {c for c in candidates if c.host_id == host_id}
        print(2, candidates)

        if port:
            candidates = {c for c in candidates if c.port == port}
        print(3, candidates)

        return candidates


class RemoteRouters(dict):
    def add(self, host_id, hostname, port, ip):
        if host_id not in self:
            self[host_id] = (hostname, port, [ip])
            return

        old_hostname, old_port, ips = self[host_id]

        if hostname != old_hostname:
            log.warn(f"New hostname for {host_id} is different. {old_hostname} -> {hostname}")

        if port != old_port:
            log.warn(f"New port for {host_id} is different. {old_port} -> {port}")

        if ip not in ips:
            ips.append(ip)

        self[host_id] = (hostname, port, ips)

    def get_hostname(self, host_id):
        return self[host_id][0]

    def remove(self, host_id):
        del self[host_id]

    def choose_ip(self, host_id):
        _, _, ips = self[host_id]
        return random.choice(ips)




"""class RemoteRouters:
    def __init__(self):
        self.hostname_map = {} # host_id -> hostname
        self.port_map = {}
        self.ip_map = {}

    def add(self, host_id, hostname, port, ip):
        if host_id in self.hostname_map:
            assert self.hostname_map[host_id] == hostname
        else:
            self.hostname_map[host_id] = hostname

        if host_id in self.port_map:
            assert self.port_map[host_id] == port
        else:
            self.port_map[host_id] = port

        if host_id in self.ip_map:
            self.ip_map[host_id].add(ip)
        else:
            self.ip_map[host_id] = {ip}

    def remove(self, host_id):
        del self.hostname_map[host_id]
        del self.port_map[host_id]
        del self.ip_map[host_id]

    def choose_ip(self, host_id):
        ips = self.ip_map[host_id]
        return random.choice(ips)

    def __iter__(self):
        yield from (
            (k, self.hostname_map[k], self.port_map[k], self.ip_map[k])
            for k in self.ip_map.keys())"""
