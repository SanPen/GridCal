# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import sys
import uvicorn
import argparse
from pathlib import Path

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from VeraGridServer.main import app
from VeraGridServer.settings import settings
from VeraGridServer.generate_ssl_key import generate_ssl_certificate, get_my_ip
from VeraGridServer.__version__ import __VeraGridServer_VERSION__


def resolve_server_runtime_file_path(file_name: str) -> str:
    """
    Resolve one server runtime file path relative to the server package directory.

    :param file_name: Candidate file path from the CLI or caller.
    :return: Absolute filesystem path.
    """
    base_directory: Path = Path(__file__).resolve().parent
    requested_path: Path = Path(file_name)

    # Relative TLS file names must live next to the server package so the
    # runtime can generate and reuse them consistently from any cwd.
    if requested_path.is_absolute() or requested_path.root:
        return str(requested_path)
    else:
        return str(base_directory / requested_path)


def start_server(key_file_name: str = "key.pem", cert_file_name: str = "cert.pem",
                 port: int = 8000, domain: str = "localhost",
                 master_host: str = "", master_port: int = 0,
                 username: str = "", password: str = "", is_master: bool = True,
                 secure: bool = True,
                 db_host: str = "", db_port: int = 0,
                 db_name: str = "", db_user: str = "", db_password: str = "",
                 db_schema: str = "veragrid",
                 seed_default_admin: bool = True,
                 default_admin_org_idtag: str = "admin",
                 default_admin_org_name: str = "admin",
                 default_admin_user_idtag: str = "admin",
                 default_admin_user_name: str = "admin",
                 default_admin_user_password: str = "veragrid is great",
                 bind_host: str | None = None) -> None:
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
    :param db_host: PostgreSQL host name.
    :param db_port: PostgreSQL port number.
    :param db_name: PostgreSQL database name.
    :param db_user: PostgreSQL user name.
    :param db_password: PostgreSQL password.
    :param db_schema: PostgreSQL schema name.
    :param seed_default_admin: Whether to (re-)seed a default admin organization/user
        on every startup. Set to false once a deployment manages its own
        organizations/users.
    :param default_admin_org_idtag: Identifier for the seeded organization row.
    :param default_admin_org_name: Display name for the seeded organization row.
    :param default_admin_user_idtag: Identifier for the seeded user row.
    :param default_admin_user_name: Display name for the seeded user row.
    :param default_admin_user_password: Bookkeeping password for the seeded user row
        (not used for authentication; the admin console and API only check the
        single instance-level password/API key).
    :param bind_host: Listening address, or the discovered IP when omitted.
    :return: None.
    """

    # find out my IP
    host: str = get_my_ip()
    listening_host: str = host if bind_host is None else bind_host
    resolved_key_file_name: str = resolve_server_runtime_file_path(file_name=key_file_name)
    resolved_cert_file_name: str = resolve_server_runtime_file_path(file_name=cert_file_name)

    print(f"""
┓┏      ┏┓  • ┓┏┓({__VeraGridServer_VERSION__} Alpha) 
┃┃┏┓┏┓┏┓┃┓┏┓┓┏┫┗┓┏┓┏┓┓┏┏┓┏┓
┗┛┗ ┛ ┗┻┗┛┛ ┗┗┻┗┛┗ ┛ ┗┛┗ ┛ 
{listening_host}:{port}
    """)

    if secure:
        generate_ssl_certificate(
            ip=host,
            domain=domain,
            key_file_name=resolved_key_file_name,
            cert_file_name=resolved_cert_file_name
        )

    # extra attributed on launch
    settings.am_i_master = is_master
    settings.master_host = master_host
    settings.master_port = master_port
    settings.this_host = host
    settings.this_port = port
    settings.this_username = username
    settings.this_password = password
    settings.db_host = db_host
    settings.db_port = db_port
    settings.db_name = db_name
    settings.db_user = db_user
    settings.db_password = db_password
    settings.db_schema = db_schema
    settings.seed_default_admin = seed_default_admin
    settings.default_admin_org_idtag = default_admin_org_idtag
    settings.default_admin_org_name = default_admin_org_name
    settings.default_admin_user_idtag = default_admin_user_idtag
    settings.default_admin_user_name = default_admin_user_name
    settings.default_admin_user_password = default_admin_user_password

    if secure:
        uvicorn.run(app,
                    host=listening_host, port=port, ssl_keyfile=resolved_key_file_name, ssl_certfile=resolved_cert_file_name)
    else:
        uvicorn.run(app,
                    host=listening_host, port=port)

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
    parser.add_argument("--db_host", type=str, default="", help="PostgreSQL host")
    parser.add_argument("--db_port", type=int, default=0, help="PostgreSQL port")
    parser.add_argument("--db_name", type=str, default="", help="PostgreSQL database name")
    parser.add_argument("--db_user", type=str, default="", help="PostgreSQL user")
    parser.add_argument("--db_password", type=str, default="", help="PostgreSQL password")
    parser.add_argument("--db_schema", type=str, default="veragrid", help="PostgreSQL schema name")
    parser.add_argument("--seed_default_admin", type=str2bool,
                        choices=[True, False], default=True,
                        help="Seed a default admin organization/user on every startup")
    parser.add_argument("--default_admin_org_idtag", type=str, default="admin",
                        help="Identifier for the seeded organization row")
    parser.add_argument("--default_admin_org_name", type=str, default="admin",
                        help="Display name for the seeded organization row")
    parser.add_argument("--default_admin_user_idtag", type=str, default="admin",
                        help="Identifier for the seeded user row")
    parser.add_argument("--default_admin_user_name", type=str, default="admin",
                        help="Display name for the seeded user row")
    parser.add_argument("--default_admin_user_password", type=str, default="veragrid is great",
                        help="Bookkeeping password for the seeded user row (not used for authentication)")

    # Parse arguments
    args = parser.parse_args()

    print("Arguments:")
    print('\n'.join(f'{k}: {v}' for k, v in vars(args).items()))

    # Call the start_server function with the parsed arguments
    start_server(key_file_name=args.key_fname,
                 cert_file_name=args.cert_fname,
                 port=args.port,
                 bind_host=args.host,
                 domain=args.host,
                 master_host=args.master_host,
                 master_port=args.master_port,
                 secure=args.secure,
                 is_master=args.master,
                 username=args.user,
                 password=args.pwd,
                 db_host=args.db_host,
                 db_port=args.db_port,
                 db_name=args.db_name,
                 db_user=args.db_user,
                 db_password=args.db_password,
                 db_schema=args.db_schema,
                 seed_default_admin=args.seed_default_admin,
                 default_admin_org_idtag=args.default_admin_org_idtag,
                 default_admin_org_name=args.default_admin_org_name,
                 default_admin_user_idtag=args.default_admin_user_idtag,
                 default_admin_user_name=args.default_admin_user_name,
                 default_admin_user_password=args.default_admin_user_password)
