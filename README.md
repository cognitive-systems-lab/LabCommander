

#  Introduction
Lab-Commander (labc) is a library to make distributed applications within a local network as easy as possible.
labc is a middleware 

The central concept of the library is to register functions on the network and make them accessibel from any other host without any boilerplate.

##  Principles
* Every node can talk to every other node
* Preferred abstraction layer are exposed functions
* Automatic discovery
* Based on asyncio / one loop per server

## Exhaustive Auto-Discovery Algorithm
1. for every local IP-address send unicast UDP package to every host in subnetworkb
2. skip local ip-addresses send UDP to broadcast-loopback instead
3. if receive unicast UDP-Package broadcast package to loopback

## Register-Call Example

Here is an example on how you can make a function available on the network with using `register` as a:

```python
import labc

@labc.register
def echo(arg):
    return arg

labc.serve()
```

And here is how you can use it by using `labc.call` in another script:
```python
import labc
labc.call("echo", "Hello World!")
```

## Publish-Subscribe 

You also expose function to a message queue.

If you subscribe a function multiple times it will be called multiple times.

```python
import labc

labc.subscribe(print)
labc.serve()
```

And here is how you can use it by using `labc.call` in another script:

```python
import labc

# this will now print a message on the server side
labc.publish("print", "Hello World!")
```

#  Remote Function

The goal of lab-commander is to make functions executable on the network.

# Services

**Interresting Stuff:**
* plugin system: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins
* `pkgutil` 
* zipimport

### Locations

Services are stored in `$HOME/.config/labc/services` (linux) or `%USERPROFILE%\AppData\Local\MyApp\services` (windows). 

```
labc install [-e] PATH
```
This will copy (or symbol-link) a file or path to the service folder.

### starting

Before remote functions can be executed or messages between services can be exchanged, a service needs to be started. Since we do not want the services to run all the time it is necessary to remotely start services from a central point. Services that are placed in one of the services folders are discoverable and can be started to several means:

1. Python

Starting a service within Python works with the `labc.load` method. It can receive a Service Name, Class or Instance. If a service name is passed it will look for a service with that name in the list of services that had been discovered. The name can be full or partially here, eg. 

2. Shell
3. ServiceControll
`labc.core.ServiceControll` is a Services that can start and shutdown other services.

```python
labc.get_host("computer1").start_service("LightControl")
labc.get_host("computer1").shutdown_service("LightControl")
```

The shutdown of a services currently simply works by unregistering, unsubscribing all its methods, notifying all hosts shutdown and deleting it from the list of loaded service.

The ServiceControll is a service itself and therefor needs to be started with the other two methods. Remotely this is best done using ssh.
    

labc can be started with a Service dedicated to load other services dynamically during at runtime. 


# why not some other middleware / technology?

- **ROS** is hard to install, requieres packes that are outside of python, it seams that for most applications it requieres a specific Ubunut version


**message-oriented middlewares**
Message Ques 
Messa AMQP, STOMP, MQTT

- autobahn / WAMP

- jsonrpc / xmlrpc

- **zmq**
    - a zmq-socket can only be used with one communication pattern at a time

- **SCTP**
    - while SCTP seem an IDEAL technology to only use one socket

- http / rest-api

- labstreaming layer

- SOAP

- dbus

- bash: pipes and 

- XMPP

- matrix.org

None of them have autodiscover and usually relay on a single broker.
 


# Specifications

## mutual server awareness
1. server-1 is aliva
2. server-2 

# dynamic discovery problem
predefined port range (or order)
- tcp discover
 - exhaustive search
- udp discover
- memorize nodes
- predefined nodes (ip & port ranges)
- router node
- Extended Pub-Sub (xpub/xsub)

# function sharing
1. function sharing service
2. public (part of the collective)
 - private (published but not part of collective)
 - local (published only to localhost)
 - secret (published to no one)

# node and function publishing algorithm
1. all nodes always know about all other nodes
2. if node gets created it needs to tells existance to collective
3. gets list of all nodes
4. notifies existence to all other notes
5. tell or request function names
6. if gets new fucntion (new services)


# labc4
## specifications
- use plain TCP sockets
- truly brokerless
- pub / sub
- req / rep
- three fundamentals: namespace resoltuion / clustering / job distribution
- design as layers around a socket (everything is a socket ??)
- modelling problem: can one instance have multiple services ? or is each endpoint a service?
- services do not create other than trough labc
- multiple services can share a socket (if in one process / thread)
- init() can be invoked manually or is invoked automatically when requiered (in SI)
- services can have dependencies (can be local or global)
- easy to install / pure python / low dependencies

## API

**Properties in modules:** https://stackoverflow.com/questions/880530/can-modules-have-properties-the-same-way-that-objects-can

## Scopes
scopes: node, host, network
The corresponding namespaces can be instantiated for each node and each host. There is only one network namespace.
Resolution options:
 - if a local function has network scope, it is automatically also located in the host and node scope
 - if functions with the same identifier appear in a namespace, choose fully randomly or choose randomly from the most local functions.
 - dont switch to smaller scope if function does not appear in bigger scope
 - this problem does not appear 
So there are cases where more specific to more genereal function resolution is usefull. Technically there needs to be only one services which informs about registrations and subscribtions in a network, however whenever possible a more local node should be employed to reduce network traffic.

```python
localhost.call("funcname", arg1, arg2, kwarg1="foo") # 

# pings node on computer1 on port 8080
get_host("computer1", 8080).publish("ping") 

# pings all nodes on computer1
get_host("computer1").publish("ping") 

# pings all nodes
network.core.ping() 

network.call_all("ping", )
```

###  call and publish

```python
def publish(topic, msg):
    pubsock.send(top, msg)
```

```python
labc.call(name, args=None, kwargs=None, scope="network", *, perspective=None, lower_scope="server", resolution_order="bottom-up")
```

###  function service
* Holds and updates informations about all remote functions on the network
* the goal is that all function services have the same

**Methods to synchronize state:**


#### get endpoint
* ask FunctionService on local server
* ask for local functions on all servers
* ask FunctionService on defualt server

* if function service in instance:
    * get req-endpoint by local call
* elif function service on root port:
    * get req-endpoint by remote call
* elif server on 5000 root ip:
    * start function service in root instance
* else:
    * start instance on root port


### modes of concurrency
* threads
* asyncio
* multiprocess
* independent processes


###  Message Types
 - request (req)
 - publish (pub)
 - reply (rep)
 - except (exc) - like a reply, only that some error occurred, should case the message handler to throw an exception
 - request-publish (reqpub) combination of request and reply. Chooses one worker to answer the request and publishes a message to all other


### core service
Informs about registrations and subscrions to other nodes (functions dont contain side effects)
 - there must always a function / core service on the root port
 - when a server instance registers a new function, the local core service is notified
 - all other cores are notified and ask new node for funtions


##  Function resolution
The current implementation includes three scope levels:


### Scopes
**server** - for functions only on the current server instance
**host** - for function on a specific host (computer)
**network** - for function visible on the entire network


### Perspectives
The general perspectives are equal to the scope levels. For specific perspectives the host or the server can be addresse individually

The function resolution happes in the FunctionPool service which also stores all information about functions registerd on the network. Resolution has a scope and a perspective. 


## Network Events
    <!-- Network variabel are a concept that can be used to  -->

### v0.0.1 basic rpc and message passing
- implement message passing (encode decode as json-dict) ✓
- include message type handling: (req, rep, pub, maybe sub) ✓
- server class ✓
- call functions with explicit location ✓
- subscribe to topics ✓
- publish to topics explicit location ✓

### v0.0.2 Services
- introduce services ✓
- core service for basic information of server ✓
- high level call function without local server ✓
- remote service to store information of known servers  ✓
- automatic port choosing  ✓
- look for services in ~/.config/labc/services and in ./services
- service starting for starting services

### v0.0.3 Auto-Discovery
- Add thread-save endpoint storage ✓
- Add exhaustive + local broadcast echo discovery ✓
- Add send request existence ✓
- Add send notify existence ✓

###  v0.0.4 Function Pool Client
- Introduce Thread-Save Client for Function Pool ✓
- blind  publish routing ✓
- blind  call routing ✓
- namespace objects ✓

### v0.0.5 Scopes 
- function resolution includes scopes ✓
- function resolution includes perspective 
- test scopes

### v0.0.6 Fault Tolerance
- publish notify_death for closing servers
- notify dead server on failed connection
- lifelines ✓

### v0.0.7 setup / cli
- introduce propper cli / with click or argparse
- create setup.py
- configuration: port range, ip
- comment default parameters in init user configuration
- set configuraiton parameters through cli
- add toml configuration

### v0.1.0 testing / documentation

### v1.0
- create man pages


### vX.x.x
- cache previously known hosts
- there needs to be an abstraction for communication for a plugin-system, which will allow bridging different middlewares

## questions / problems
- discuss relative addressing / visibility / clustering
- parameter order in register and subscribe
- put message meta information into object?

## notes
implement recv all for regular sockets: https://stackoverflow.com/questions/17667903/python-socket-receive-large-amount-of-data

## Terms

**telecommunications network** is a group of [nodes](https://en.wikipedia.org/wiki/Node_%28networking%29 "https://en.wikipedia.org/wiki/Node_(networking)") interconnected by [links](https://en.wikipedia.org/wiki/Link_%28telecommunications%29 "https://en.wikipedia.org/wiki/Link_(telecommunications)") that are used to exchange messages between the nodes

**node** ([Latin](https://en.wikipedia.org/wiki/Latin) _nodus_, ‘knot’) is either a redistribution point or a [communication endpoint](https://en.wikipedia.org/wiki/Communication_endpoint)

**host** - computer connected to a network. Every host is a node, but not every node is a host.

**endpoint** - 


# labc5
The difference to its predecessor is the omission of the UDP service discovery. The system has a dedicated router server running on the main port (default 55555) instead. If a client issues a request it will be forwarded to the corresponding endpoint. If the endpoint is on the local host, the request is send to the server where the function is hosted, if the function is on a remote host it will be forwarded to the corresponding  server.

## thoughts
I am still not sure about the nature of a router. There are several options:

1. The router is a service.
    - this would however require to alter the call to router or the router itself
2. The router is distinct and not a function-server.
    - might not make use of _labc_ at all
    - this has the disadvantage, that I cannot use the handy _labc_ syntax to add functionality
    - advantage: highlights the distinct role of the router
3. The router is an extension to (inherits from) a function-server.
	- advantage: I can use _labc_ syntax
	- advantage: distinct role
	- disadvantage: router has probability more functionality than it really needs
4. Router is an altered version of a server (some extensions / some reductions)
    - this is a mix of 2. and 3., there will be a common base-serer class
    - a roter would not have services
6. Function-server and router are identical. (router functionality is integrated into the function-server)
	- disadvantage: no distinct role

## matching topics to subscribers
* https://bravenewgeek.com/category/data-structures/
		* conclusion: use _trie_ data-structure for topic matching

## discovery
1. request existence -> return uid
2. request function records
3. notify existence -> send IPs

I am still not sure if the router should be a modified kind of a server, or a service in a server.
 
## ToDo
- [ ] Add routing to server
- [ ] If a router is in unaltered 


## Network Discovery:

There are several ways how autodiscovery could work:

* _Use hard-coded endpoint strings_, i.e., fixed IP addresses and agreed ports. This worked in internal networks a decade ago when there were a few “big servers” and they were so important they got static IP addresses. These days however it’s no use except in examples or for in-process work (threads are the new Big Iron). You can make it hurt a little less by using DNS but this is still painful for anyone who’s not also doing system administration as a side-job.
    
* _Get endpoint strings from configuration files_. This shoves name resolution into user space, which hurts less than DNS but that’s like saying a punch in the face hurts less than a kick in the groin. You now get a non-trivial management problem. Who updates the configuration files, and when? Where do they live? Do we install a distributed management tool like Salt Stack?
    
* _Use a message broker_. You still need a hard-coded or configured endpoint string to connect to the broker, but this approach reduces the number of different endpoints in the network to one. That makes a real impact, and broker-based networks do scale nicely. However, brokers are single points of failure, and they bring their own set of worries about management and performance.
    
* _Use an addressing broker_. In other words use a central service to mediate address information (like a dynamic DNS setup) but allow nodes to send each other messages directly. It’s a good model but still creates a point of failure and management costs.
    
* _Use helper libraries, like ZeroConf_, that provide DNS services without any centralized infrastructure. It’s a good answer for certain applications but your mileage will vary. Helper libraries aren’t zero cost: they make it more complex to build the software, they have their own restrictions, and they aren’t necessarily portable.
    
* _Build system-level discovery_ by sending out ARP or ICMP ECHO packets and then querying every node that responds. You can query through a TCP connection, for example, or by sending UDP messages. Some products do this, like the Eye-Fi wireless card.
    
* _Do user-level brute-force discovery_ by trying to connect to every single address in the network segment. You can do this trivially in ZeroMQ since it handles connections in the background. You don’t even need multiple threads. It’s brutal but fun, and works very well in demos and workshops. However it doesn’t scale, and annoys decent-thinking engineers.
    
* _Roll your own UDP-based discovery protocol_. Lots of people do this (I counted about 80 questions on this topic on StackOverflow). UDP works well for this and it’s technically clear. But it’s technically tricky to get right, to the point where any developer doing this the first few times will get it dramatically wrong.
    
* _Gossip discovery protocols_. A fully-interconnected network is quite effective for smaller numbers of nodes (say, up to 100 or 200). For large numbers of nodes, we need some kind of gossip protocol. That is, where the nodes we can reasonable discover (say, on the same segment as us), tell us about nodes that are further away. Gossip protocols go beyond what we need these days with ZeroMQ, but will likely be more common in the future. One example of a wide-area gossip model is mesh networking.

In *labc* a varyity of different discovery methods will be employed. The discovery methods can be specified in the configuration files, by setting IP and port ranges.
The standard methods will work by specifying a standart (or root) port, which will always hold the first instance of a labc server on a computer. Other than having a dedicated port, the root-server is not special. The root-server will then scan the specified port and ip ranges for a remote-server. If a remote server is found it will be ask for all known hosts (which is assumed to hold all existing labc servers on the network) and notify them of their existance and ask from their exposed functions and subscriptions. Following labc servers on the same host will get the list of all known labc-servers on the network from the root-server.
There are still many race-condition problems that need to be solved first.


# Theory / Discussion

## Multicast
* Other than broadcast receivers can show interest
* True vs replicated Multicast (n-times unicast)
* Source IP-addr is identical to unicast address
* Target address is a multicast-group
* Class D address space
    * 224.0.0.0 - 239.255.255.255
    * flat IP-space (no concept of subnetworks)



# Outlook
The successor of _labc_ should be _Metabridge_, which can connect to all common IPC middleware / interfaces by 

## Design-Pattern in IPC

* Message passing
* Message queue
* Named Pipe


## License

`labc` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
#  Introduction
Lab-Commander (labc) is a library to make distributed applications within a local network as easy as possible.
labc is a middleware 

The central concept of the library is to register functions on the network and make them accessibel from any other host without any boilerplate.


