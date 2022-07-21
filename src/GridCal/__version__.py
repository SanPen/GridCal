# do not forget to keep a three-number version!!!
import datetime
_current_year_ = datetime.datetime.now().year

__GridCal_VERSION__ = "4.5.5"

url = 'https://github.com/SanPen/GridCal'

about_msg = "GridCal v" + str(__GridCal_VERSION__) + '\n\n'

about_msg += """
GridCal has been carefully crafted since 2015 to 
serve as a platform for research and consultancy. 
Visit https://gridcal.org for more details.\n"""

about_msg += """
This program is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

The source of GridCal can be found at:
""" + url + "\n\n"

copyright_msg = 'Copyright (C) 2015-' + str(_current_year_) + ' Santiago Peñate Vera'

contributors_msg = 'Michel Lavoie (Transformer automation)\n'
contributors_msg += 'Bengt Lüers (Better testing)\n'
contributors_msg += 'Josep Fanals Batllori (HELM)\n'
contributors_msg += 'Manuel Navarro Catalán (Better documentation)\n'
contributors_msg += 'Paul Schultz (Grid Generator)\n'
contributors_msg += 'Andrés Ramiro (Optimal net transfer capacity)\n'
contributors_msg += 'Ameer Carlo Lubang (Improved short-circuit)\n'

about_msg += copyright_msg + '\n' + contributors_msg
