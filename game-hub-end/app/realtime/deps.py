"""实时通道 FastAPI 依赖。"""

from app.core.websocket.protocols import AuthenticationPort
from app.realtime.realtime_authentication_adapter import (
    AccessTokenAuthenticationAdapter,
)


def get_authentication_port() -> AuthenticationPort:
    """
    组装 WebSocket 认证端口依赖。

    :return: ``AuthenticationPort`` 实例。
    """
    return AccessTokenAuthenticationAdapter()
