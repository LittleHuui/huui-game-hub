"""WebSocket 消息模型。"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class RealtimeMessage(BaseModel):
    """平台实时通道统一消息结构。"""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, description="消息类型")
    requestId: Optional[str] = Field(default=None, description="请求 ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="消息载荷")
    timestamp: int = Field(description="毫秒时间戳")
