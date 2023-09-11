

# Loading Services

Services are a way to bundle function registrations and subscriptions. 

```python
class TestClass:
    
    @register
    def ping(self):
        return "pong"

    @subscribe
    def notify(self, arg):
        print("Notified:", arg)
```

The `load` functions loads an object as a service. The behavior of loads differs
depending on the type of the first argument.


# Service Discovery
Services can be discovery automatically when they are placed on certain locations
in the file-system. 

* User-Level services are placed in the config-folder
  + Unix-like systems: `~/.local/share/labc/services`
  * Windows: ...
  
Modules or packages within this folders are imported by *labc* and classes with the `@register_class` decorator are added to the class-registry.  If a services module or the files of a service package keep unchanged since the last *labc* 


# Applications

Applications are a collection of services and are defined in toml files. Applications can be automaticaly lunched in a seperate realm.


```toml
[[application]]
name = "SampleApp"
services = ["TestService1","TestService2"]
parameter1 = "foo"
```