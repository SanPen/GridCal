# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import socket
import requests
from fastapi import APIRouter

from GridCalServer.settings import settings


def get_local_ip():
    try:
        return socket.gethostbyname(socket.gethostname())  # Gets internal IP
    except Exception:
        return "127.0.0.1"  # Fallback to localhost


def register_with_master(host: str, port: int, this_port: int, username: str, password: str):
    """
    register this service with a master service
    :param host:
    :param port:
    :param this_port:
    :param username:
    :param password:
    :return:
    """

    url = f"{host}:{port}/register_child_server"

    worker_data = {
        "ip": get_local_ip(),  # Detect IP dynamically
        "port": this_port,  # Set worker's port
        "username": username,
        "password": password,
    }

    response = requests.post(url,
                             json=worker_data,
                             verify=False,
                             timeout=5)
    response.raise_for_status()
    return response.json()  # Return JSON response


def lifespan(app: APIRouter):
    """
    Function that is called once the app starts.
    :param app:
    :return:
    """
    if not settings.am_i_master:
        print("I am a child service")
        res = register_with_master(host=settings.master_host,
                                   port=settings.master_port,
                                   this_port=settings.this_port,
                                   username=settings.this_username,
                                   password=settings.this_password)
        print("registering response:", res)
    else:
        print("I am the master service")

    yield  # The application runs here


router = APIRouter(lifespan=lifespan)
