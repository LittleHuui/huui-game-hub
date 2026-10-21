"""房间对局命令模型。"""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.strategy_turn.schemas import ActionSubmission


class RoomActionCommand(BaseModel):
    """房间层动作命令，承载幂等与版本信息。"""

    model_config = ConfigDict(extra="forbid")

    requestId: str = Field(min_length=1, description="客户端幂等请求 ID")
    baseVersion: int = Field(ge=0, description="客户端已知对局版本号")
    submission: ActionSubmission = Field(description="动作提交意图")
