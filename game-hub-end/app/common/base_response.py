"""公共请求模型。"""

from pydantic import BaseModel, ConfigDict, Field


class PageRequest(BaseModel):
    """
    分页查询公共入参；业务分页请求类应继承此类，禁止重复定义分页字段。

    校验：``pageNum >= 1``、``1 <= pageSize <= 100``。
    """

    model_config = ConfigDict(populate_by_name=True)

    pageNum: int = Field(default=1, ge=1, description="页码，从 1 开始")
    pageSize: int = Field(default=20, ge=1, le=100, description="每页条数，最大 100")
