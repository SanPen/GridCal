# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import datetime
_current_year_ = datetime.datetime.now().year

# do not forget to keep a three-number version!!!
__GridCalServer_VERSION__ = "5.3.19"

url = 'https://github.com/SanPen/GridCal'

about_msg = "GridCalServer v" + str(__GridCalServer_VERSION__) + '\n\n'

about_msg += """
GridCal has been carefully crafted since 2015 to 
serve as a platform for research and consultancy.\n"""

about_msg += """
This program is free software; you can redistribute it and/or
modify it subject to the terms of the Mozilla Public License, v. 2.0. 
If a copy of the MPL was not distributed with this file, 
You can obtain one at https://mozilla.org/MPL/2.0/.

The source of GridCal can be found at:
""" + url + "\n\n"
