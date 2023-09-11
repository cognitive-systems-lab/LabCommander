# Server-Router Communication

**Function-Records**

* type
* host-id
* port
* name
* scope
* realm

**Router Components**

{
    host-id
    hostname
    ip_addr
    port
    known_peers
    discover_from_subnets
}

1. routing table
2. local_servers
3. local_function_records
4. remote_routers

---

# Actions

**new router**
- initiate router handshake
- add to remote routers
- add frecs to all other router's routing table
---
**remove router**
- remove from all remote router records
- remove frecs from other routers with host-id
---
**add server**
- add entry to `router.servers`
- add to frecs to `router.function_records`
- add to frecs to `router.routing_table`
---
**remove server**
1. broadcast `remove_server` message with server idenfication (host_id + port) to remote routers
2. remove frecs from `router.routing_table`
2. remove local `router.routing_table`

---
**dynamically add function records**
- ...

---
**dynamically remove function recrods**
- ...


**call**
1. send req-packet to router
2. router matches fitting records from routing table
3. select one record
4. get location of record
    * local: forward request to server
    * remote: forward request to remote router
6. receive reply
7. send reply to back to client
8. done


**publish**
1. send pub-packet to router
2. router matches fitting records from routing table
3. for every record
4. get location of record
    * local
        1. forward request to server
    * remote
        1. forward request to remote router
6. done