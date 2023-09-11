"""
Utility functiond for network communictaion.
"""

from contextlib import closing
import inspect
import ipaddress
import json
import logging
import platform
import re
import socket
import subprocess
from typing import NamedTuple

import psutil

from .util import RemoteCallError, RemoteEncodingError, RemoteNameError

try:
    import coloredlogs
    coloredlogs_available = True
except ImportError:
    coloredlogs_available = False

log = logging.getLogger(__name__)

TCP_DEFAULT_BUFFERSIZE = 1024


class RemoteFunctionRecord(NamedTuple):
    type: str
    name: str
    scope: str
    realm: str
    host_id: str
    port: int


def loads_json(msg):
    """
    Loads json string. For empty string returns empty dict.
    """
    if len(msg) == 0:
        return {}
    else:
        return json.loads(msg)


def send_obj(host, port, obj):
    """
    Sends an object to an endpoint.
    """
    port = int(port)
    msg = json.dumps(obj) + "\n"
    data = msg.encode()
    s = socket.socket()
    s.connect((host, port))
    s.sendall(data)
    s.close()


def send_recv_obj(host, port, obj):
    """
    Sends an object to an endpoint and receives a response.
    """
    port = int(port)
    msg = json.dumps(obj) + "\n"
    data = msg.encode()
    s = socket.socket()
    s.connect((host, port))
    s.sendall(data)
    data = recvall(s)
    s.close()
    msg = data.decode()
    obj = loads_json(msg)
    return obj


def recvall(sock, buffersize=None):
    if buffersize is None:
        buffersize = TCP_DEFAULT_BUFFERSIZE
    data = bytearray()
    while True:
        packet = sock.recv(buffersize)
        if not packet:
            break
        data.extend(packet)
    return data


def check_up(port):
    """
    Sends an empty message to check if server is up and runnning.
    """
    try:
        send_obj("localhost", port, {})
    except:
        return False
    else:
        return True


def request(host, port, name, args=None, kwargs=None):
    """
    Low level implementation of direct remote procedure call.
    """
    packet = {
        "type": "req",
        "name": name,
        "args": args or [],
        "kwargs": kwargs or {},
    }
    res = send_recv_obj(host, port, packet)
    return res


def call(host, port, name, args=None, kwargs=None):
    """
    Encapsulated request.
    """
    reply = request(host, port, name, args, kwargs)
    return handle_reply(reply, name)


def handle_reply(reply, name):
    if reply["type"] == "rep":
        return reply["value"]

    if reply["type"] == "err":
        if reply["value"] == "RemoteNameError":
            raise RemoteNameError(f"No registration for '{name}'.")
        elif reply["value"] == "RemoteCallError":
            raise RemoteCallError("Execution of function failed on server site.")
        elif reply["value"] == "RemoteEncodingError":
            raise RemoteEncodingError("JSON serialization on Client site failed.")
        else:
            raise Exception(f"Unknown error-type: {reply['value']}")


def publish(host, port, name, args=None, kwargs=None):
    """
    Low level implementation message publishing.
    """
    packet = {
        "type": "pub",
        "name": name,
        "args": args or [],
        "kwargs": kwargs or {},
    }
    send_obj(host, port, packet)

"""
def create_lifeline(host, port):
    " ""Blocks until connection is canceled." ""
    packet = {
        "type": "lifeline",
    }
    send_recv_obj(host, port, packet)
"""

def is_port_in_use(port, *, timeout=0.1, host="localhost"):
    port = int(port)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # TODO maybe actually send some data here
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def get_inet_addrs(skip_localhost=True):
    """
    Get all IP4 addresses of current host.
    """
    addresses = []
    net_if_stats = psutil.net_if_stats()
    for if_name, snicaddr_list in psutil.net_if_addrs().items():
        if not net_if_stats[if_name].isup:
            # log.info(f"Skip interface {if_name}")
            continue
        for snicaddr in snicaddr_list:
            if not snicaddr.family == socket.AF_INET:
                # skip non IP4 addresses
                continue
            addr = ipaddress.ip_address(snicaddr.address)
            if skip_localhost and addr.is_loopback:
                continue
            addresses.append(addr)
    return addresses


def get_subnets_from_network_interfaces():
    """
    Returns discoverd subnet-addresses with ip addresses of local network interfaces.
    """

    return {
        ipaddress.ip_interface(ip_addr.exploded + "/24").network
        for ip_addr in get_inet_addrs()
    }


def get_subnets_from_route():
    """
    Parses the routing table to discover subnetworks and assigns an ip address of a network adapter.
    In a VPN this discovered more subnets.
    """

    # TODO: add Windows and Mac support: try ´route´ command

    # obtain routing table
    table = subprocess.check_output(["ip", "route", "show"], text=True).split('\n')
    table = (row.split() for row in table if row.strip())

    # filter subnet addresses
    subnets = []
    via_routed = []
    for row in table:
        addr, *rest = row
        if not addr.endswith("/24"):
            continue # not a subnetwork
        props = dict(zip(rest[::2], rest[1::2]))

        assert ("src" in props) ^ ("via" in props) # either ´src´ or ´via´ must be in props

        if "src" in props:
            subnets.append((addr, props["src"]))
        else:
            via_routed.append((addr, props["via"]))

    # assign via routed subnets to a local network interface ip address
    new_subnets = []
    for via_subnet_addr, via_addr in via_routed:
        ipaddress.ip_address(via_addr)
        via_addr_obj = ipaddress.ip_address(via_addr)
        for subnet_addr, src_addr in subnets:
            subnet_obj = ipaddress.ip_network(subnet_addr)
            if via_addr_obj in subnet_obj:
                new_subnets.append((via_subnet_addr, src_addr))
    subnets.extend(new_subnets)

    return {addr[0] for addr in subnets}


def get_peers_from_tailnet():
    """
    Return ip_address -> hostname for all active tailscale peers.
    """

    cmd = ["tailscale", "status", "--json"]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception(result.stderr.decode())
    ts_status = json.loads(result.stdout.decode())
    v4ips = {}
    for peer in ts_status["Peer"].values():
        v4ips[peer["HostName"]] = [
            ip for ip in peer["TailscaleIPs"]
            if ipaddress.ip_address(ip).version == 4]

    # TODO: Why would a host have more then one IP ? And what would be the appropriate response ?
    # filter one ip-addrs per host
    addrs = [ipaddress.ip_address(addr[0]) for addr in v4ips.values() if addr]
    
    return addrs


def get_peers_from_hostsfile(filter_inet6=True, *, return_errors=False):
    """
    Parses /etc/hosts file and returns all the hostnames in a list.
    """

    # Ref: https://www.howtogeek.com/27350/beginner-geek-how-to-edit-your-hosts-file/
    if platform.system() == "Windows":
        path = "C:\Windows\System32\drivers\etc"
    else:
        path = "/etc/hosts"

    with open(path, 'r') as f:
        hostlines = f.readlines()
    hostlines = [line.strip() for line in hostlines
                 if not line.startswith('#') and line.strip() != '']
    hosts = []
    for line in hostlines:
        inet_addr, *hostnames = line.split('#')[0].split()
        hosts.append([inet_addr, hostnames])
    
    error_group = []
    ip_addrs = set()
    for ip_addr, _ in hosts:
        try:
            ip_addr = ipaddress.ip_address(ip_addr)
        except ValueError as e:
            error_group.append(e)
        else:
            if filter_inet6 and (ip_addr.version == 6):
                continue

            if ip_addr.is_loopback:
                continue

            ip_addrs.add(ip_addr)
    
    if return_errors:
        return ip_addrs, error_group
    else:
        return ip_addrs


def parse_address_range(addr, default_port=None):
    """
    Parse an ip4 address or ip4 address range (in CIDR notation), with possibly stating the port.

    e.g.: 192.168.2.5/24:12345

    """

    # TODO: introduce port ranges.
    # TODO: replace assertions with proport exceptions

    assert addr, "Empty address."
    assert addr[0] not in ":/", "Target address cannot start with slash or collon."
    assert addr.count(":") <= 1, "Target address can only contain on collon."
    assert addr.count("/") <= 1, "Target address can only contain on slash."

    addr = addr.strip()
    host = r"(?P<host>[^/:]*)"
    port = r"(:(?P<port>\d*))"
    block = r"(/(?P<block>\d*))"
    pattern = re.compile(fr"^{host}{block}?{port}?$")
    host, block, port = pattern.match(addr).groupdict().values()

    if block is None:
        block = 32
    else:
        assert block.isdigit(), "Block is not a number, but {block}"
        block = int(block)
        assert 0 <= block <= 32, "IP-block definitions in CIDR notation must be between 0 and 32."

    if port is None:
        port = default_port
    else:
        assert port.isdigit(), "Port is not a number, but {port}."
        port = int(port)
        assert 0 <= port <= 65535, "Port must be between 0 and 65535."

    ip = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    hostname = r"\w*" # [a-zA-Z0-9_]
    pattern = re.compile(fr"^(?P<host>{ip}|{hostname})$")
    match = pattern.match(host)
    assert match, f"Invalid hostname or IPv4-Address: {host}"

    return host, block, port


def is_valid_host_address(inet_addr):
    """
    Filters IP-Addresses that cannot be a host address.
    """
    if isinstance(inet_addr, str):
        inet_addr = ipaddress.ip_address(inet_addr)
    # TODO: fix this !! 
    #is_broadcast = (inet_addr == ipaddress.ip_network(inet_addr).broadcast_address)
    is_broadcast = False
    return not (is_broadcast or inet_addr.is_multicast or inet_addr.is_loopback)


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def get_sockopts(sock, err_val=None):
    prefixes = {
        "SOL_SOCKET": "SO_",
        "IPPROTO_IP": "IP_",
        "IPPROTO_TCP": "TCP_",
    }
    out = {}
    import socket
    for lev, prefix in prefixes.items():
        opt_res = {}
        opt_names = [option for option in dir(socket) if option.startswith(prefix)]
        for oname in opt_names:
            try:
                val = sock.getsockopt(socket.__dict__[lev], socket.__dict__[oname])
            except OSError:
                val = err_val
            opt_res[oname] = val
        if any(val is not None for val in opt_res.values()):
            out[lev] = opt_res
    return out


def call_with_conf(callable_, conf):
    """
    Calls a callable with parameters from a dictionary.
    """

    def get_value(para):
        if para.name in conf:
            arg = conf[para.name]
        elif para.default != para.empty:
            arg = para.default
        else:
            raise TypeError("Parameter \'{para.name}\': missing configuration or deafult value.")
        return arg

    sig = inspect.signature(callable_)
    args = []
    kwargs = {}
    for para in sig.parameters.items():
        if para.kind == para.POSITIONAL:
            args.append(get_value(para))
        elif para.kind in (para.KEYWORD or para.POSITIONAL_OR_KEYWORD):
            kwargs[para.name] = get_value(para)
        elif para.kind == para.VAR_KEYWORD:
            new_kwargs = conf.get(para.name, {})
            new_kwargs.update(kwargs)
            kwargs = new_kwargs
        elif para.kind == para.VAR_POSITIONAL:
            ...
        else:
            ...


def check_interface(interface):
    """
    Checks for an interace beening up or down.
    
    Stolen from: https://stackoverflow.com/questions/17679887/python-check-whether-a-network-interface-is-up
    """
    interface_addrs = psutil.net_if_addrs().get(interface) or []
    return socket.AF_INET in [snicaddr.family for snicaddr in interface_addrs]



def ensure_encode(packet):
    """
    Ensures that an object is encoded as a binary json string.
    """
    if not isinstance(packet, (str, bytes)):
        packet = json.dumps(packet)
    if isinstance(packet, str):
        packet = packet.encode()
    return packet


def ensure_decode(packet):
    """
    Ensures that an object is decoded as a binary json string.
    """
    if isinstance(packet, bytes):
        packet = packet.decode()
    if isinstance(packet, str):
        packet = json.loads(packet)
    return packet


def get_arguments(packet):
    """
    Return args and kwargs from a packet.
    """
    args = packet.get('args', [])
    kwargs = packet.get('kwargs', {})
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
    return args, kwargs
