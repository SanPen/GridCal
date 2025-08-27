# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from fastapi import APIRouter, HTTPException

# Dictionary to store registered services
registered_services = dict()

router = APIRouter()


@router.post("/register_child_server")
async def register_child_server(data: dict):
    try:
        # data = await request.json()  # Parse JSON manually
        ip = data.get("ip", None)
        port = data.get("port", None)
        username = data.get("username", None)
        password = data.get("password", None)

        key = f"{username}:{ip}:{port}"

        if ip is None or port is None:
            raise HTTPException(status_code=400, detail="Missing 'ip' or 'port'")

        if key in registered_services:
            raise HTTPException(status_code=400, detail="Service already registered")

        # Store the service information
        registered_services[key] = {"ip": ip, "port": port}

        return {"message": "Service registered successfully", "service": username, "ip": ip, "port": port}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")


@router.get("/registered_child_servers")
def get_registered_child_servers():
    """
    Return all registered services
    :return:
    """
    if not registered_services:
        raise HTTPException(status_code=404, detail="No services registered")
    return registered_services
