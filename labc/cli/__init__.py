# SPDX-FileCopyrightText: 2022-present Meier, Moritz <mome@uni-bremen.de>
#
# SPDX-License-Identifier: MIT

from pathlib import Path

import click

from ..__about__ import __version__, get_git_branch

from .route import route
from .configure import configure
from .serve import serve
from .list import list
from .status import status
from .subscribe import subscribe
from .publish import publish


git_branch, git_commit = get_git_branch()

labc_path = Path(__file__).parent.parent

if git_branch:
    help_message = f"%(prog)s, version %(version)s from {labc_path} (git branch: {git_branch}, commit: {git_commit})"
else:
    help_message = f"%(prog)s, version %(version)s from {labc_path}"


class AliasedGroup(click.Group):
    """
    Alias for each sub-command with the three leading letters.
    # stolen from: https://click.palletsprojects.com/en/8.1.x/advanced/
    """

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [
            x for x in self.list_commands(ctx)
            if (len(cmd_name) == 3 and x.startswith(cmd_name)) or (x == cmd_name)
        ]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")
    
    def resolve_command(self, ctx, args):
        # always return the full command name
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name, cmd, args



@click.group(cls=AliasedGroup, context_settings={'help_option_names': ['-h', '--help']}, invoke_without_command=False)
@click.version_option(version=__version__, prog_name='labc', message=help_message)
@click.pass_context
def labc(ctx: click.Context):
    pass

labc.add_command(route)
labc.add_command(configure)
labc.add_command(serve)
labc.add_command(list)
labc.add_command(status)
labc.add_command(subscribe)
labc.add_command(publish)
