from fastapi import Depends, FastAPI

from .router import room, user

app = FastAPI()
app.include_router(user.router)
app.include_router(room.router)

# Sample APIs
@app.get("/")
async def root():
    return {"message": "Hello World"}
