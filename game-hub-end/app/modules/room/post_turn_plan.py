"""回合后任务计划。"""

from pydantic import BaseModel, ConfigDict, Field


class PostTurnPlan(BaseModel):
    """回合结束后待调度的后台任务计划。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str = Field(min_length=1, description="房间 ID")
    version: int = Field(ge=0, description="提交后的对局版本号")
    reason: str = Field(min_length=1, description="调度原因")
    gameCode: str = Field(default="", description="游戏编码")
    currentPlayerId: str = Field(default="", description="当前行动玩家 ID")
    phase: str = Field(default="", description="对局阶段")
    enqueuedAtMs: int = Field(ge=0, description="入队时间戳（毫秒）")
