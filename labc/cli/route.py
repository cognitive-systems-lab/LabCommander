
import click
import setproctitle

try:
    from click_help_colors import HelpColorsCommand
    command_cls = HelpColorsCommand
except:
    command_cls = None

from ..router import Router, is_router_running
from ..router import __name__ as router_log_name
from .. import state


@click.command(
    cls=command_cls,
    short_help="Start a router.")
@click.option("--daemon", "-d", "run_as_daemon", is_flag=True, help="Run server in the background.")
#@click.option("--config", "-c", "config_file", help="Configuration file.")
def route(run_as_daemon):
    conf_dict = state.config["router"]
    setproctitle.setproctitle("labc-router") 
    if run_as_daemon:
        if is_router_running():
            import logging
            log = logging.getLogger(router_log_name)
            log.error(f"Router already running on port {conf_dict['port']}")
        else:
            from daemon import DaemonContext
            with DaemonContext():
                Router(**conf_dict).start()
    else:
        Router(**conf_dict).start()
