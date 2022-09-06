from fastapi import Request
from fastapi.responses import JSONResponse


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


def InvalidTokenHandler(request: Request, exception: InvalidToken) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "Token is invalid."})
