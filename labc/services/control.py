from labc import (
    register,
    register_service,
    load,
    # unload,
    list_available_services,
)

"""
Three options to design a service controll:
1. The shutdown (i.e. remove from server) functionality is a method of the service object
2. There is a special service control service which can shutdown (and possibly start) other services
3. Starting / Stopping services is a native funtionaly of the server (needs an introduction of server-messages/calls, which is currently not a thing.)
"""

# TODO: make all of this asyncronous

@register_service(name="labc.Control")
class ControllableService:
    def __init__(self):
        print("sample service created")
    
    @register
    def load(service, route_name: str = None, args=None, kwargs=None) -> None:
        """
        Load a service
        """
        load(service, route_name, args, kwargs)

    @register
    def unload(self, service_name):
        """
        Unload a service
        """
        unload(service_name)

    @register
    def list_availabel_services(self):
        """
        Get a list of available services
        """
        return list_available_services()
    