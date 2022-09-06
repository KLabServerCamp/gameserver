from fastapi import FastAPI

from .exceptions import InvalidToken, InvalidTokenHandler
from .routers import room, user

app = FastAPI()
app.include_router(user.router)
app.include_router(room.router)

app.add_exception_handler(InvalidToken, InvalidTokenHandler)


# Sample APIs
@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}
