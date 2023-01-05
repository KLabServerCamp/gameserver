from fastapi import FastAPI
from .router import user, room

app = FastAPI()

# Sample APIs
app.include_router(user.router, prefix="/user", tags=["api"])
app.include_router(room.router, prefix="/room", tags=["api"])


@app.get("/")
async def root():
    return {"message": "Hello World"}
