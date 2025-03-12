# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
from hashlib import sha256
from fastapi import FastAPI, Header, HTTPException, Response, Query
from fastapi.responses import FileResponse

from GridCalServer.endpoints import register_in_master
from GridCalServer.endpoints import register_sub_servers
from GridCalServer.endpoints import calculations
from GridCalServer.endpoints import jobs
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from datetime import datetime, timedelta
import ipaddress

app = FastAPI()
app.include_router(register_in_master.router)
app.include_router(register_sub_servers.router)
app.include_router(calculations.router)
app.include_router(jobs.router)

# Store WebSocket connections in a set
__connections__ = set()

# GC_FOLDER = get_create_gridcal_folder()
# GC_SERVER_FILE = os.path.join(GC_FOLDER, "server_config.json")
SECRET_KEY = ""


def verify_api_key(api_key: str = Header(None)):
    """
    Define a function to verify the API key
    :param api_key:
    """
    if api_key is None:
        raise HTTPException(status_code=401, detail="API Key is missing")

    # Hash the provided API key using the same algorithm and compare with the stored hash
    hashed_api_key = sha256(api_key.encode()).hexdigest()
    if hashed_api_key != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")



@app.get("/get_cert")
def get_cert():
    """
    Get the certificate from the server
    :return:
    """
    # Serve the certificate file
    return FileResponse("cert.pem",
                        media_type="application/x-pem-file",
                        filename="cert.pem")

@app.get("/")
async def read_root():
    """
    Root
    :return: string
    """
    return {"message": "GridCal server running", "status": "ok"}


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    """

    :return:
    """
    return FileResponse(os.path.join(os.path.dirname(__file__), "data", "GridCal_icon.ico"))
