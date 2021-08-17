# do not forget to keep a three-number version!!!
import datetime
_current_year_ = datetime.datetime.now().year

__GridCal_VERSION__ = "4.2.0a21"

url = 'https://github.com/SanPen/GridCal'

about_msg = "GridCal v" + str(__GridCal_VERSION__) + '\n\n'

about_msg += """
GridCal has been carefully crafted since 2015 to 
serve as a platform for research and consultancy. 
Visit https://gridcal.org for more details.\n"""

about_msg += """
This program comes with ABSOLUTELY NO WARRANTY. 
This is free software, and you are welcome to 
redistribute it under certain conditions.\n
GridCal is licensed under the GNU general public 
license V.3. See the license file for more 
details.

The source of GridCal can be found at:
""" + url + "\n\n"

copyright_msg = 'Copyright (C) 2015-' + str(_current_year_) + ' Santiago Peñate Vera'

contributors_msg = 'Michel Lavoie (Transformer automation)\n'
contributors_msg += 'Bengt Lüers (Better testing)\n'
contributors_msg += 'Josep Fanals Batllori (HELM)\n'
contributors_msg += 'Manuel Navarro Catalán (Better documentation)\n'
contributors_msg += 'Paul Schultz (Grid Generator)\n'

about_msg += copyright_msg + '\n' + contributors_msg
