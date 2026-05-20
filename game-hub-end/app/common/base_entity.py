"""实体响应公共基础字段。"""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class BaseEntityResponse(BaseModel):
    """
    数据库实体读模型的公共字段；业务响应类应继承此类，禁止重复定义基础字段。

    时间字段均为 Unix 毫秒时间戳（``int``），禁止返回展示用时间字符串。
    构造时须使用 camelCase 字段名；ORM 转换在 module 层显式完成。
    """

    model_config = ConfigDict(extra="forbid")

    serverId: str
    clientId: Optional[str] = None
    createdAt: int
    updatedAt: int
    deletedAt: Optional[int] = None
