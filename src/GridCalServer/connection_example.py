import os
import asyncio
import websockets
from typing import Callable


async def send_large_file(file_path: str,
                          websocket: websockets.WebSocketClientProtocol,
                          progress_func: Callable[[float], None] = None) -> None:
    """
    Send a large file via web-socket
    :param file_path: local file path
    :param websocket: web socket instance
    :param progress_func: Progress function
    :return: None
    """
    # Get the size of the file
    file_size = os.path.getsize(file_path)
    bytes_sent = 0

    # Open the file in binary mode
    with open(file_path, "rb") as file:
        # Read the file in chunks
        while True:
            # Read 4KB of data
            data = file.read(4096)
            if not data:
                break  # End of file

            # Send the chunk over the WebSocket
            await websocket.send(data)

            # Update bytes sent
            bytes_sent += len(data)

            # Calculate progress
            progress = (bytes_sent / file_size) * 100

            if progress_func is not None:
                progress_func(progress)


async def connect_and_send(file_path: str, url: str = 'ws://localhost:8000/ws'):
    """
    Connect and send data to web-socket
    """
    async with websockets.connect(url) as websocket:
        await send_large_file(file_path, websocket)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(connect_and_send(file_path="my_file.dat", url="ws://localhost:8000"))
