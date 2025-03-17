# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import sys
import uvicorn
import argparse

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from GridCalServer.main import app
from GridCalServer.settings import settings
from GridCalServer.generate_ssl_key import generate_ssl_certificate, get_my_ip
from GridCalServer.__version__ import __GridCalServer_VERSION__


def start_server(key_file_name: str = "key.pem", cert_file_name: str = "cert.pem",
                 port: int = 8000, domain="localhost",
                 master_host: str = "", master_port: int = 0,
                 username: str = "", password: str = "", is_master: bool = True,
                 secure: bool = True):
    """
    Start server function
    :param key_file_name: name of the key file that the server generates
    :param cert_file_name: name of the certificate file that the server generates
    :param port: Port to serve (8000 usually)
    :param domain: Domain to serve (i.e. localhost)
    :param master_host: IP address to register the server to (if this runs in child mode)
    :param master_port: Port to register the server to (if this runs in child mode)
    :param username: Username to authenticate with
    :param password: Password to authenticate with
    :param is_master: Whether the server is master or not
    :param secure: Whether the server is secure or not (if it looks for the certificates or not)
    """

    # find out my IP
    host = get_my_ip()

    print(f"""
┏┓  • ┓┏┓  ┓┏┓ ({__GridCalServer_VERSION__} Alpha) 
┃┓┏┓┓┏┫┃ ┏┓┃┗┓┏┓┏┓┓┏┏┓┏┓
┗┛┛ ┗┗┻┗┛┗┻┗┗┛┗ ┛ ┗┛┗ ┛
{host}:{port}  
    """)

    if secure:
        generate_ssl_certificate(
            ip=host,
            domain=domain,
            key_file_name=key_file_name,
            cert_file_name=cert_file_name
        )

    # extra attributed on launch
    settings.am_i_master = is_master
    settings.master_host = master_host
    settings.master_port = master_port
    settings.this_host = host
    settings.this_port = port
    settings.this_username = username
    settings.this_password = password

    if secure:
        uvicorn.run(app,
                    host=host, port=port, ssl_keyfile=key_file_name, ssl_certfile=cert_file_name)
    else:
        uvicorn.run(app,
                    host=host, port=port)


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
    start_server(key_file_name=args.key_fname,
                 cert_file_name=args.cert_fname,
                 master_host=args.host,
                 master_port=args.port)
