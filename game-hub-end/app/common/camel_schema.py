"""HTTP 请求/响应 camelCase 模型配置。"""

from pydantic import ConfigDict

CAMEL_MODEL_CONFIG = ConfigDict(extra="forbid")
