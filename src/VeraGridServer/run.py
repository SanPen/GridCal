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

from VeraGridServer.main import app
from VeraGridServer.settings import settings
from VeraGridServer.generate_ssl_key import generate_ssl_certificate, get_my_ip
from VeraGridServer.__version__ import __VeraGridServer_VERSION__


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
┓┏      ┏┓  • ┓┏┓({__VeraGridServer_VERSION__} Alpha) 
┃┃┏┓┏┓┏┓┃┓┏┓┓┏┫┗┓┏┓┏┓┓┏┏┓┏┓
┗┛┗ ┛ ┗┻┗┛┛ ┗┗┻┗┛┗ ┛ ┗┛┗ ┛ 
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

def str2bool(value):
    if isinstance(value, bool):
        return value
    if value.lower() in {'True', 'true', 't', 'yes', '1'}:
        return True
    elif value.lower() in {'False', 'false', 'f', 'no', '0'}:
        return False
    else:
        raise argparse.ArgumentTypeError(f'Invalid boolean value: {value}')

if __name__ == "__main__":
    # Initialize parser
    parser = argparse.ArgumentParser(description="Start a secure VeraGrid server")

    # Add arguments
    parser.add_argument("--key_fname", type=str, default="key.pem",
                        help="Path to the private key file that the server generates")
    parser.add_argument("--cert_fname", type=str, default="cert.pem",
                        help="Path to the certificate file that the server generates")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host IP address")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")

    parser.add_argument("--secure", type=str2bool,
                        choices=[True, False], default=True, help="Use https?")

    parser.add_argument("--master", type=str2bool,
                        choices=[True, False], default=True, help="Use https?")

    parser.add_argument("--master_host", type=str, default="0.0.0.0", help="URL of the master instance")
    parser.add_argument("--master_port", type=int, default=80, help="Port of the master instance")
    parser.add_argument("--user", type=str, default="", help="username")
    parser.add_argument("--pwd", type=str, default="", help="Password")

    # Parse arguments
    args = parser.parse_args()

    print("Arguments:")
    print('\n'.join(f'{k}: {v}' for k, v in vars(args).items()))

    # Call the start_server function with the parsed arguments
    start_server(key_file_name=args.key_fname,
                 cert_file_name=args.cert_fname,
                 port=args.port,
                 domain=args.host,
                 master_host=args.master_host,
                 master_port=args.master_port,
                 secure=args.secure,
                 is_master=args.master,
                 username=args.user,
                 password=args.pwd)
