
import logging
from pathlib import Path
import sys
import subprocess as sp

import click

try:
    from click_help_colors import HelpColorsCommand
    command_cls = HelpColorsCommand
except:
    command_cls = None

from .. import api
    

log = logging.getLogger(__name__)


@click.command(cls=command_cls, short_help="Start a new server.")
@click.argument('services', nargs=-1)
@click.option("--daemon", "-d", "run_as_daemon", is_flag=True, help="Run server in the background.")
def serve(services, run_as_daemon):
    """Load services and run server."""
    #if "services" in map(str, Path().iterdir()):
    #    api.find_services('services')
    for s in services:
        api.load(s)
    if run_as_daemon:
        if sys.platform == "win32":
            log.error(f"Cannot run as daemon on Windows!")
            """
            if sys.argv[0] == "pythonw":
                # is already started in the background
                api.serve()
            else:
                # run with same argument but using pythonw instead
                cmd = ["pythonw", "-m" , "labc", *sys.argv[1:]]
                print(cmd)
                sp.run(cmd)
                print("process finished")
            """
        else:
            if sys.platform != "linux":
                log.warning(f"Dameon has not been tried on platorm: {sys.platform}")
            from daemon import DaemonContext
            with DaemonContext():
                api.serve()
    else:
        api.serve()
