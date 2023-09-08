from enum import IntEnum

from pydantic import BaseModel


class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class LiveJudge(BaseModel):
    perfect: int
    great: int
    good: int
    bad: int
    miss: int
