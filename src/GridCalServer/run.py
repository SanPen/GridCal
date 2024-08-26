# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import os
import sys
import uvicorn

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))
from GridCalServer.__version__ import about_msg
from GridCalServer.endpoints import app
from GridCalServer.generate_ssl_key import generate_ssl_certificate


def start_server(key_fname: str = "key.pem", cert_fname: str = "cert.pem", host: str = "0.0.0.0", port: int = 8000):
    """

    :param key_fname:
    :param cert_fname:
    :param host:
    :param port:
    :return:
    """

    if not os.path.exists(key_fname) or not os.path.exists(cert_fname):
        generate_ssl_certificate(key_fname=key_fname, cert_fname=cert_fname)

    uvicorn.run(app, host=host, port=port, ssl_keyfile=key_fname, ssl_certfile=cert_fname)


if __name__ == "__main__":
    print(about_msg)
    start_server()
