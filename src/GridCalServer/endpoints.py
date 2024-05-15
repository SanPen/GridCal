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
from hashlib import sha256
from fastapi import FastAPI, WebSocket, Header, HTTPException
from fastapi.responses import FileResponse
from GridCalEngine.IO.file_system import get_create_gridcal_folder

app = FastAPI()

# Store WebSocket connections in a set
__connections__ = set()

GC_FOLDER = get_create_gridcal_folder()
GC_SERVER_FILE = os.path.join(GC_FOLDER, "server_config.json")
SECRET_KEY = ""


# Define a function to verify the API key
def verify_api_key(api_key: str = Header(None)):
    if api_key is None:
        raise HTTPException(status_code=401, detail="API Key is missing")

    # Hash the provided API key using the same algorithm and compare with the stored hash
    hashed_api_key = sha256(api_key.encode()).hexdigest()
    if hashed_api_key != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")


@app.get("/")
async def read_root():
    """
    Root
    :return: string
    """
    return {"message": "GridCal server running", "status": "ok"}


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(os.path.dirname(__file__), "data", "GridCal_icon.ico"))


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """

    :param websocket:
    """
    await websocket.accept()
    __connections__.add(websocket)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            # Broadcast message to all connected clients
            for connection in __connections__:
                await connection.send_text(data)
    except Exception:
        __connections__.remove(websocket)
