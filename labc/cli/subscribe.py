
import logging

import click


from ..router import is_router_running

from .. import api
from .. import util


log = logging.getLogger(__name__)





@click.command(short_help="Subscribe to a labc topic.")
@click.argument('topic', default="", nargs=1)
def subscribe(topic):
    """Subscribe stdout to a topic"""

    print("hello here")

    def print_(*args, **kwargs):
        print(util.args2str(*args, **kwargs))

    api.subscribe(print_, topic=topic)
    api.serve()




