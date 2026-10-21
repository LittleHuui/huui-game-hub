"""一致对局状态读取模型。"""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.strategy_turn.schemas import RuntimeSnapshot


class ConsistentGameState(BaseModel):
    """同一提交边界内的运行时快照与对局版本。"""

    model_config = ConfigDict(extra="forbid")

    snapshot: RuntimeSnapshot = Field(description="运行时快照")
    gameVersion: int = Field(ge=0, description="对局版本号")
