"""平台统一错误码定义。"""

class ErrorCodeItem(object):
    """
    单个错误码项，包含数值码与默认提示文案。

    :param code: 业务错误码。
    :param message: 默认人类可读信息。
    """

    __slots__ = ("code", "message")

    def __init__(self, code, message):
        self.code = int(code)
        self.message = str(message)

    def __repr__(self):
        return "ErrorCodeItem(code={0}, message={1!r})".format(self.code, self.message)


class ErrorCode(object):
    """平台统一错误码（按模块分段）。"""

    # 1000x 通用
    COMMON_ERROR = ErrorCodeItem(10001, "通用错误")
    PARAM_ERROR = ErrorCodeItem(10002, "参数错误")
    SYSTEM_ERROR = ErrorCodeItem(10003, "系统错误")

    # 2000x 用户
    USER_NOT_FOUND = ErrorCodeItem(20001, "用户不存在")
    USERNAME_ALREADY_EXISTS = ErrorCodeItem(20002, "用户名已存在")
    USER_DISABLED = ErrorCodeItem(20003, "用户已禁用")

    # 3000x 游戏
    GAME_NOT_FOUND = ErrorCodeItem(30001, "游戏不存在")
    GAME_DISABLED = ErrorCodeItem(30002, "游戏已禁用")
    GAME_PROP_NOT_FOUND = ErrorCodeItem(30003, "游戏道具不存在")

    # 4000x 钱包
    WALLET_NOT_FOUND = ErrorCodeItem(40001, "钱包不存在")
    BALANCE_NOT_ENOUGH = ErrorCodeItem(40002, "积分余额不足")

    # 5000x 购买
    PURCHASE_ALREADY_EXISTS = ErrorCodeItem(50001, "购买记录已存在")

    # 6000x 同步
    SYNC_EVENT_TYPE_UNSUPPORTED = ErrorCodeItem(60001, "不支持的同步事件类型")
    SYNC_DATA_INVALID = ErrorCodeItem(60002, "同步数据无效")

    # 7000x 对局
    MATCH_NOT_FOUND = ErrorCodeItem(70001, "对局不存在")

    # 8000x 排行榜
    RANKING_QUERY_ERROR = ErrorCodeItem(80001, "排行榜查询失败")


def list_error_codes():
    """
    列出当前已注册的全部错误码项。

    :return: ``(属性名, ErrorCodeItem)`` 列表。
    """
    items = []
    for name in dir(ErrorCode):
        if name.startswith("_"):
            continue
        value = getattr(ErrorCode, name)
        if isinstance(value, ErrorCodeItem):
            items.append((name, value))
    return sorted(items, key=lambda pair: pair[1].code)


def error_code_catalog():
    """
    生成错误码目录文本，便于文档与排查。

    :return: 每行 ``名称 code=数值 message=文案`` 的多行字符串。
    """
    lines = []
    for name, item in list_error_codes():
        lines.append("{0} code={1} message={2}".format(name, item.code, item.message))
    return "\n".join(lines)
