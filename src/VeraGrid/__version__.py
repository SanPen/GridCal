# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import datetime
_current_year_ = datetime.datetime.now().year

# remember to keep a three-number version!!!
__VeraGrid_VERSION__ = "5.4.0"

url = 'https://github.com/SanPen/VeraGrid'

about_msg = "VeraGrid v" + str(__VeraGrid_VERSION__) + '\n\n'

about_msg += """
VeraGrid has been carefully crafted since 2015 to 
serve as a platform for research and consultancy.\n"""

about_msg += """
This program is free software; you can redistribute it and/or
modify it subject to the terms of the Mozilla Public License, v. 2.0. 
If a copy of the MPL was not distributed with this file, 
You can obtain one at https://mozilla.org/MPL/2.0/.

The source of VeraGrid can be found at:
""" + url + "\n\n"

