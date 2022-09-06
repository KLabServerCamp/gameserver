from fastapi import FastAPI

from .room import router as room_router
from .user import router as user_router

app = FastAPI()
app.include_router(room_router, prefix="/room", tags=["room"])
app.include_router(user_router, prefix="/user", tags=["user"])

# Sample APIs


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}
