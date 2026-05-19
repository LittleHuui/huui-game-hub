"""实体响应公共基础字段。"""

from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class BaseEntityResponse(BaseModel):
    """
    数据库实体读模型的公共字段；业务响应类应继承此类，禁止重复定义基础字段。

    时间字段均为 Unix 毫秒时间戳（``int``），禁止返回展示用时间字符串。
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    serverId: str = Field(validation_alias=AliasChoices("server_id", "serverId"))
    clientId: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("client_id", "clientId"),
    )
    createdAt: int = Field(validation_alias=AliasChoices("created_at", "createdAt"))
    updatedAt: int = Field(validation_alias=AliasChoices("updated_at", "updatedAt"))
    deletedAt: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("deleted_at", "deletedAt"),
    )
