"""HTTP 请求 camelCase 字段工具。"""

import re
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field


CAMEL_MODEL_CONFIG = ConfigDict(extra="forbid", populate_by_name=True)


def camel_to_snake(name: str) -> str:
    """
    将 camelCase 转为 snake_case。

    :param name: camelCase 字段名。
    :return: snake_case 字段名。
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def camel_alias(name: str) -> AliasChoices:
    """
    生成同时接受 camelCase 与 snake_case 的校验别名。

    :param name: 主字段名（camelCase）。
    :return: Pydantic ``AliasChoices``。
    """
    return AliasChoices(name, camel_to_snake(name))


def camel_field(name: str, **kwargs: Any) -> Any:
    """
    创建兼容 camelCase / snake_case 入参的 Field。

    :param name: 主字段名（camelCase）。
    :param kwargs: 传给 ``Field`` 的其它参数。
    :return: Pydantic Field 实例。
    """
    return Field(validation_alias=camel_alias(name), **kwargs)
