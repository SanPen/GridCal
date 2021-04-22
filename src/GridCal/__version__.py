# do not forget to keep a three-number version!!!
import datetime
_current_year_ = datetime.datetime.now().year

__GridCal_VERSION__ = "4.1.0"

url = 'https://github.com/SanPen/GridCal'

about_msg = "GridCal v" + str(__GridCal_VERSION__) + '\n\n'

about_msg += "GridCal has been carefully crafted since 2015 to serve as a platform for research and consultancy.\n\n"

about_msg += 'This program comes with ABSOLUTELY NO WARRANTY. \n'
about_msg += 'This is free software, and you are welcome to redistribute it under certain conditions; '

about_msg += "GridCal is licensed under the GNU general public license V.3. "
about_msg += 'See the license file for more details. \n\n'
about_msg += "The source of GridCal can be found at:\n" + url + "\n\n"

about_msg += 'Copyright (C) 2015-' + str(_current_year_) + '\nSantiago Peñate Vera\n'
about_msg += 'Michel Lavoie (Transformer automation)\n'
about_msg += 'Bengt Lüers (Better testing)\n'
about_msg += 'Josep Fanals Batllori (HELM)\n'
about_msg += 'Manuel Navarro Catalán (Better documentation)\n'
about_msg += 'Paul Schultz (Grid Generator)\n'
