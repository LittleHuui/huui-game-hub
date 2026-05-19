"""服务端唯一 ID 生成。"""

import uuid


def generate_server_id(prefix: str) -> str:
    """
    生成带前缀的服务端唯一 ID。

    :param prefix: ID 前缀，例如 user、wallet_ledger。
    :return: 形如 ``prefix_<hex>`` 的字符串。
    """
    return f"{prefix}_{uuid.uuid4().hex}"
