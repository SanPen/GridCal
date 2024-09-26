# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os
import sys
import uvicorn
import argparse

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from GridCalServer.endpoints import app
from GridCalServer.generate_ssl_key import generate_ssl_certificate


def start_server(key_fname: str = "key.pem", cert_fname: str = "cert.pem", host: str = "0.0.0.0", port: int = 8000):
    """
    Start server function
    :param key_fname: name of the key file that the server generates
    :param cert_fname: name of the certificate file that the server generates
    :param host: Hosting ip (localhost ussually)
    :param port: Port to serve (8000 ussually)
    """
    print("""
┏┓  • ┓┏┓  ┓┏┓          
┃┓┏┓┓┏┫┃ ┏┓┃┗┓┏┓┏┓┓┏┏┓┏┓
┗┛┛ ┗┗┻┗┛┗┻┗┗┛┗ ┛ ┗┛┗ ┛
                    (Alpha) 
    """)

    if not os.path.exists(key_fname) or not os.path.exists(cert_fname):
        generate_ssl_certificate(key_fname=key_fname, cert_fname=cert_fname)

    uvicorn.run(app, host=host, port=port, ssl_keyfile=key_fname, ssl_certfile=cert_fname)


if __name__ == "__main__":
    # Initialize parser
    parser = argparse.ArgumentParser(description="Start a secure GridCal server")

    # Add arguments
    parser.add_argument("--key_fname", type=str, default="key.pem",
                        help="Path to the private key file that the server generates")
    parser.add_argument("--cert_fname", type=str, default="cert.pem",
                        help="Path to the certificate file that the server generates")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host IP address")
    parser.add_argument("--port", type=int, default=8001, help="Port to run the server on")

    # Parse arguments
    args = parser.parse_args()

    # Call the start_server function with the parsed arguments
    start_server(key_fname=args.key_fname,
                 cert_fname=args.cert_fname,
                 host=args.host,
                 port=args.port)

