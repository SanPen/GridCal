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
import json
from hashlib import sha256
from fastapi import FastAPI, WebSocket, Header, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse
from GridCalEngine.IO.file_system import get_create_gridcal_folder
from GridCalEngine.IO.gridcal.pack_unpack import parse_gridcal_data, gather_model_as_jsons

app = FastAPI()

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


async def stream_load_json(json_data):
    """

    :param json_data:
    :return:
    """
    async def generate():
        """

        """
        yield json.dumps(json_data).encode()

    return StreamingResponse(generate())


async def process_json_data(json_data):
    """

    :param json_data:
    """
    circuit = parse_gridcal_data(data=json_data)
    print(f'Circuit loaded alright nbus{circuit.get_bus_number()}, nbr{circuit.get_branch_number()}')


@app.post("/upload/")
async def upload_json_background(json_data: dict, background_tasks: BackgroundTasks):
    """

    :param json_data:
    :param background_tasks:
    :return:
    """
    background_tasks.add_task(stream_load_json, json_data)
    background_tasks.add_task(process_json_data, json_data)

    return {"message": "JSON data streaming initiated"}


@app.websocket("/process_file")
async def process_file(websocket: WebSocket):
    """

    :param websocket:
    :return:
    """
    await websocket.accept()

    # Receive JSON data
    # Buffer to accumulate received chunks
    json_buffer = b""

    # Receive JSON data in chunks
    async for chunk in websocket.iter_bytes():
        json_buffer += chunk
        # Check if the end of JSON data is reached (e.g., by checking for a delimiter)
        # Here, we assume that the end of JSON data is marked by an empty chunk
        if not chunk:
            break

    # Deserialize the JSON data
    try:
        print("start: ", json_buffer[0:5].decode(encoding='utf-8'))
        print("end: ", json_buffer[-5:].decode(encoding='utf-8'))
        json_data = json.loads(json_buffer.decode(encoding='utf-8'))

        json_ok = True
    except json.decoder.JSONDecodeError as e:
        print("Json parse error:", e)
        json_ok = False
        json_data = dict()

    if json_ok:
        if "sender_id" in json_data:

            circuit = parse_gridcal_data(data=json_data)
            print('Circuit loaded alright')

            # await websocket.send_text("File and JSON data received successfully")
        else:
            print("No sender_id found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
