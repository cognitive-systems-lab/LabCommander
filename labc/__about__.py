# SPDX-FileCopyrightText: 2022-present Meier, Moritz <mome@uni-bremen.de>
#
# SPDX-License-Identifier: MIT
__version__ = '0.5.1'


def get_git_branch():
    """
    Tries to determine the current git branch by using the calling the git CLI.
    """
    import subprocess as sp
    from pathlib import Path
    module_folder = Path(__file__).parent
    cmd = f"cd {module_folder} && git rev-parse --abbrev-ref HEAD"
    branch = sp.run(cmd, capture_output=True, shell=True).stdout.decode().strip()
    cmd = f"cd {module_folder} && git rev-parse --short HEAD"
    commit = sp.run(cmd, capture_output=True, shell=True).stdout.decode().strip()
    return branch, commit
