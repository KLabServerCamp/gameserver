from enum import Enum
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomUser,
    SafeUser,
    WaitRoomStatus,
)
from .router import room, user

app = FastAPI()
app.include_router(user.router)
app.include_router(room.router)

# Sample APIs
@app.get("/")
async def root():
    return {"message": "Hello World"}
