from fastapi import Request
from fastapi.responses import JSONResponse


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class InvalidJudgeResult(Exception):
    """プレイ結果が不正だったときに投げる"""


def InvalidTokenHandler(request: Request, exception: InvalidToken) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "Token is invalid."})


def InvalidJudgeResultHandler(
    request: Request, exception: InvalidToken
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Judge count result is invalid. Length of judge_count_list must be 5."
        },
    )
