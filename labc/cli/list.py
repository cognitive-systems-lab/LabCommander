
import click
import socket

try:
    from click_help_colors import HelpColorsCommand
    command_cls = HelpColorsCommand
except:
    command_cls = None

from .. import api
from .. import util
from .. import router

@click.command(
    cls=command_cls,
    short_help="List components.")
@click.argument("type", type=click.Choice(["funcs", "services", "routers"]), default="funcs")
@click.option("--fullpath", "-f", "fullpath", is_flag=True, help="Show paths without escape characters.")
def list(type, fullpath):
    if type == "funcs":
        try:
            table = router.router_call("routing-table")
        except ConnectionRefusedError:
            print("Router not running.")
        else:

            if table:
                remote_routers = router.router_request("remote-routers")["value"]
                new_table = []
                for row in table:
                    if row.host_id == util.get_host_id():
                        hostname = socket.gethostname()
                    else:
                        hostname = remote_routers[row.host_id][0]
                    new_row = (row.type, row.name, row.scope, hostname, row.port, row.realm)
                    new_table.append(new_row)
                util.print_as_table(
                    "type name scope hostname port realm",
                    new_table,
                    replace_empty = "*")
            else:
                print("No functions found in local router.")

    elif type == "services":
        services = api.list_available_services()
        if not fullpath:
            services = [(*head, util.escape_path(path)) for *head, path in services]
        util.print_as_table("name class path", services)

    elif type == "routers":
        if router.is_router_running():
            remote_routers = router.router_request("remote-routers")["value"]

            table = [[rid, *rest, ", ".join(addrs)] for rid, (*rest, addrs) in remote_routers.items()]

            # breakpoint()

            util.print_as_table(
                "id hostname port inet-addrs",
                table,
            )
        else:
            print("Router not running.")
 
