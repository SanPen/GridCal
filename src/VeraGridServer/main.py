# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import hmac
from pathlib import Path
from fastapi import Depends, FastAPI, Header, HTTPException, Response, Query
from fastapi.responses import FileResponse, RedirectResponse

from VeraGridServer.endpoints import register_in_master
from VeraGridServer.endpoints import register_sub_servers
from VeraGridServer.interactive import WebSessionManager
from VeraGridServer.endpoints import circuits, interactive_calculations, ws_telemetry
from VeraGridServer.endpoints.file_management import verify_api_key_header
from VeraGridServer.endpoints.objects import create_objects_router
from VeraGridServer.endpoints import calculations
from VeraGridServer.endpoints import jobs
from VeraGridServer.endpoints import admin
from VeraGridServer.endpoints import file_management
from VeraGridServer.db.database import create_veragrid_schema, log_database_operation
from VeraGridServer.settings import settings
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from datetime import datetime, timedelta
import ipaddress

app = FastAPI()
app.state.circuit_sessions = WebSessionManager()
app.include_router(circuits.router, dependencies=[Depends(verify_api_key_header)])
app.include_router(interactive_calculations.router, dependencies=[Depends(verify_api_key_header)])
app.include_router(create_objects_router(), dependencies=[Depends(verify_api_key_header)])
app.include_router(ws_telemetry.router)
app.include_router(register_in_master.router)
app.include_router(register_sub_servers.router)
app.include_router(calculations.router)
app.include_router(jobs.router)
app.include_router(admin.router)
app.include_router(file_management.router)

# Store WebSocket connections in a set
__connections__ = set()


def get_server_runtime_path(file_name: str) -> Path:
    """
    Resolve one runtime artifact path relative to the server package directory.

    :param file_name: Artifact file name or relative path.
    :return: Absolute filesystem path.
    """
    base_directory: Path = Path(__file__).resolve().parent
    requested_path: Path = Path(file_name)

    # Relative runtime artifacts must follow the server package directory so
    # routes and startup code do not depend on the caller working directory.
    if requested_path.is_absolute():
        return requested_path
    else:
        return base_directory / requested_path


@app.on_event("startup")
async def ensure_database_schema_on_startup() -> None:
    """
    Create the configured PostgreSQL database and schema on server startup.

    :return: None.
    """
    database_settings = settings.get_database_settings()

    if database_settings is None:
        log_database_operation(
            "Server startup skipped database creation because the database settings are incomplete."
        )
    else:
        create_veragrid_schema(
            settings=database_settings,
            seed_default_admin=settings.seed_default_admin,
            default_admin_org_idtag=settings.default_admin_org_idtag,
            default_admin_org_name=settings.default_admin_org_name,
            default_admin_user_idtag=settings.default_admin_user_idtag,
            default_admin_user_name=settings.default_admin_user_name,
            default_admin_user_password=settings.default_admin_user_password,
        )

def verify_api_key(api_key: str = Header(None)):
    """
    Define a function to verify the API key
    :param api_key:
    """
    if api_key is None:
        raise HTTPException(status_code=401, detail="API Key is missing")

    expected_api_key: str = settings.this_password

    if len(expected_api_key) == 0:
        raise HTTPException(status_code=503, detail="API key verification is not configured")

    if not hmac.compare_digest(api_key, expected_api_key):
        raise HTTPException(status_code=403, detail="Invalid API Key")



@app.get("/get_cert")
def get_cert() -> FileResponse:
    """
    Download the server certificate when it exists.

    :return: Certificate file response.
    """
    cert_path: Path = get_server_runtime_path(file_name="cert.pem")

    # Missing certificates are an expected deploy-time state, so the endpoint
    # must fail as a normal HTTP 404 instead of raising inside FileResponse.
    if cert_path.exists():
        return FileResponse(str(cert_path),
                        media_type="application/x-pem-file",
                        filename="cert.pem")
    else:
        raise HTTPException(status_code=404, detail="Certificate file not found")

@app.get("/")
async def read_root():
    """
    Root
    :return: string
    """
    return RedirectResponse(url="/admin", status_code=303)


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    """

    :return: Favicon response.
    """
    icon_path: Path = get_server_runtime_path(file_name="data/VeraGrid_icon.ico")
    return FileResponse(str(icon_path))
