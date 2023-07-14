import fastapi.exception_handlers
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from .routers import room_router, user_router

app = FastAPI()


# リクエストのvalidation errorをprintする
# このエラーが出たら、リクエストのModel定義が間違っている
@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(req: Request, exc: RequestValidationError):
    print("Request validation error")
    print(f"{req.url=}\n{exc.body=}\n{exc=!s}")
    return await fastapi.exception_handlers.request_validation_exception_handler(
        req, exc
    )


# Sample API
@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


app.include_router(user_router.router, prefix="/user")
app.include_router(room_router.router, prefix="/room")
