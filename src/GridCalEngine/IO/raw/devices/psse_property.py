# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import TypeVar
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.base.base_property import BaseProperty


class PsseProperty(BaseProperty):
    """
    Psse Property
    """

    def __init__(self,
                 property_name: str,
                 rawx_key: str,
                 class_type: TypeVar,
                 unit: Unit,
                 denominator_unit: Unit = None,
                 description: str = '',
                 max_chars=None,
                 min_value=-1e20,
                 max_value=1e20,
                 format_rule=None):

        BaseProperty.__init__(self,
                              property_name=property_name,
                              class_type=class_type,
                              unit=unit,
                              denominator_unit=denominator_unit,
                              description=description,
                              max_chars=max_chars,
                              min_value=min_value,
                              max_value=max_value)

        self.rawx_key = rawx_key
        self.format_rule = format_rule

    def __str__(self):

        return f'PSSeProp:{self.property_name}'
