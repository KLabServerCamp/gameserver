import fastapi.exception_handlers
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from .routers import room, user

app = FastAPI()
app.include_router(user.router)
app.include_router(room.router)


# リクエストのvalidation errorをprintする
# このエラーが出たら、リクエストのModel定義が間違っている
@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(req, exc):
    print("Request validation error")
    print(f"{req.url=}\n{exc.body=}\n{exc=!s}")
    return await fastapi.exception_handlers.request_validation_exception_handler(
        req, exc
    )


# Sample API
@app.get("/")
async def root() -> dict:
    return {"message": "Hello World"}
