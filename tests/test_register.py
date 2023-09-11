import labc.state
from labc import register


def ping():
    return "pong"

register(ping)

class Test1:
    @register
    def foo():
        return "bar"

@register
class Test2:
    @register(scope="host")
    def blub():
        return "yeah"