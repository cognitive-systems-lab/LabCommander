# SPDX-FileCopyrightText: 2022-present Meier, Moritz <mome@uni-bremen.de>
#
# SPDX-License-Identifier: MIT

# importing configuration first, because it will be anyway
# also some exceptions are were not reported correctly before
from . import configuration

from .api import *
network = get_namespace(scope="network")
host = get_namespace(scope="host")
server = get_namespace(scope="server")
