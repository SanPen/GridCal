# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import datetime
_current_year_ = datetime.datetime.now().year

# do not forget to keep a three-number version!!!
__GridCalEngine_VERSION__ = "5.2.7"

url = 'https://github.com/SanPen/GridCal'

about_msg = "GridCal v" + str(__GridCalEngine_VERSION__) + '\n\n'

about_msg += """
GridCal has been carefully crafted since 2015 to 
serve as a platform for research and consultancy. 
Visit https://www.advancedgridinsights.com/gridcal for more details.\n"""

about_msg += """
This program is free software; you can redistribute it and/or
modify it subject to the terms of the Mozilla Public License, v. 2.0. 
If a copy of the MPL was not distributed with this file, 
You can obtain one at https://mozilla.org/MPL/2.0/.

The source of GridCal can be found at:
""" + url + "\n\n"

copyright_msg = 'Copyright (C) 2015-' + str(_current_year_) + ' Santiago Peñate Vera'

contributors_msg = 'Michel Lavoie (Transformer automation)\n'
contributors_msg += 'Bengt Lüers (Better testing)\n'
contributors_msg += 'Josep Fanals Batllori (HELM, Sequence Short circuit)\n'
contributors_msg += 'Manuel Navarro Catalán (Better documentation)\n'
contributors_msg += 'Paul Schultz (Grid Generator)\n'
contributors_msg += 'Andrés Ramiro (Optimal net transfer capacity)\n'
contributors_msg += 'Ameer Carlo Lubang (Sequence short-circuit)\n'

about_msg += copyright_msg + '\n' + contributors_msg
