from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any
import uvicorn

app = FastAPI()

@app.post("/receive-json")
async def receive_json(data: Any):
    return {"message": "JSON received successfully", "received_data": data}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)