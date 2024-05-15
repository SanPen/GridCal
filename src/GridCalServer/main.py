from fastapi import FastAPI, WebSocket

app = FastAPI()

# Store WebSocket connections in a set
connections = set()

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.add(websocket)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            # Broadcast message to all connected clients
            for connection in connections:
                await connection.send_text(data)
    except Exception:
        connections.remove(websocket)