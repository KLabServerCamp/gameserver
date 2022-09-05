from fastapi import FastAPI

from .routers import room, user

app = FastAPI()
app.include_router(user.router)
app.include_router(room.router)


# Sample APIs
@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}
