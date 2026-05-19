"""分页响应结构。"""

from typing import Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    """
    分页数据载荷（Pydantic v2 泛型模型）。

    分页接口声明示例：``response_model=ApiResponse[PageResponse[UserResponse]]``。
    """

    model_config = ConfigDict(from_attributes=True)

    pageNum: int = Field(description="当前页码，从 1 开始")
    pageSize: int = Field(description="每页条数")
    total: int = Field(description="符合条件的总记录数")
    items: List[T] = Field(description="当前页数据列表")
