
import logging

import click

try:
    from click_help_colors import HelpColorsCommand
    command_cls = HelpColorsCommand
except:
    command_cls = None

from ..router import is_router_running

from .. import api
    

log = logging.getLogger(__name__)


@click.command(cls=command_cls, short_help="Get lab-commander status.")
@click.argument('services', nargs=-1)
def status(services):
    """
    Prints a summary of the current status of lab commander.
    """
    
    # 1. router running
    # 2. list of known routers

    if not is_router_running():
        print("Router is not running.")
    else:
        print("Router is running.")

    



