import uvicorn
from fastapi import FastAPI

from config import API_HOST, API_PORT
from routers import bots

app = FastAPI(title="Partner VPS Orchestrator", version="1.0.0")
app.include_router(bots.router)


if __name__ == "__main__":
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=False)
