"""排行榜域 Pydantic 模型。"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LeaderboardRow(BaseModel):
    """仓储层返回的排行榜原始行（服务层组装名次与响应）。"""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    nickname: str
    score: int
    duration_ms: Optional[int] = None
    created_at: int
    payload_json: Optional[str] = None


class LeaderboardEntry(BaseModel):
    """排行榜单行展示数据。"""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(description="从 1 开始的名次")
    userId: str
    nickname: str
    score: int
    durationMs: Optional[int] = None
    createdAt: int


class LeaderboardResponse(BaseModel):
    """排行榜查询响应体。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    mode: str
    difficultyCode: Optional[str] = None
    items: List[LeaderboardEntry]
