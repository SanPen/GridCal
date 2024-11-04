# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

class BaseCircuit:

    def __init__(self):
        pass

    def get_class_properties(self):
        return list()

    def get_objects_list(self, elm_type):
        return getattr(self, elm_type)
