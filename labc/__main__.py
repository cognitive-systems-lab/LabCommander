# SPDX-FileCopyrightText: 2022-present Meier, Moritz <mome@uni-bremen.de>
#
# SPDX-License-Identifier: MIT
import sys

if __name__ == '__main__':
    from .cli import labc

    sys.exit(labc())
