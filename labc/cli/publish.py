
import logging

import click


from ..router import is_router_running

from .. import api
    

log = logging.getLogger(__name__)


@click.command(short_help="Publish to a topic")
@click.argument('message', nargs=-1)
@click.option("--topic", "-t",   default="", nargs=1)
def publish(message, topic):
    """Subscribe stdout to a topic"""

    try:
        api.publish(topic, args=message)
    except ConnectionRefusedError:
        print("Router not running.")

