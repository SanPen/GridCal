# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class ExtraSettings:
    def __init__(self):
        self.am_i_master: bool = True
        self.master_host: str = ""
        self.master_port = 0
        self.this_port = 0
        self.this_username = ""
        self.this_password = ""


settings = ExtraSettings()