"""动作交互上下文。"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.strategy_turn.schemas import StrategyTurnRuntimeRule


class ActionInteractionContext(BaseModel):
    """动作交互层统一上下文。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str = Field(min_length=1, description="游戏编码")
    roomId: Optional[str] = Field(default=None, description="房间 ID")
    runtimeRule: StrategyTurnRuntimeRule = Field(description="运行时规则")
    state: Dict[str, Any] = Field(default_factory=dict, description="运行时状态")
    playerId: str = Field(min_length=1, description="交互玩家 ID")
    version: int = Field(default=0, ge=0, description="房间版本")
    currentTimeMs: int = Field(default=0, ge=0, description="本次请求统一时间")
