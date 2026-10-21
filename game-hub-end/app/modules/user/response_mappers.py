"""用户与设置响应投影。"""
from typing import Optional
from app.modules.user.models import UserAccount, UserSystemSetting
from app.modules.user.schemas import UserGameSettingRead
from app.modules.user.response_schemas import UserSummaryResponse, UserSystemSettingJson, UserSystemSettingResponse, UserGameSettingResponse


def parse_user_system_setting_json(raw: Optional[str]) -> UserSystemSettingJson:
    """
    将数据库 setting_json 解析为启动模块响应结构。

    :param raw: 原始 JSON 文本。
    :return: 解析成功则返回对象，否则返回默认值。
    """
    if raw is None or not str(raw).strip():
        return UserSystemSettingJson()
    try:
        return UserSystemSettingJson.model_validate_json(raw)
    except Exception:
        return UserSystemSettingJson()

def to_user_summary(user: UserAccount) -> UserSummaryResponse:
    """
    将用户 ORM 转为启动模块用户摘要。

    :param user: 用户账号实体。
    :return: ``UserSummaryResponse``。
    """
    return UserSummaryResponse(
        serverId=user.server_id,
        clientId=user.client_id,
        username=user.username,
        nickname=user.nickname,
        avatar=user.avatar,
        status=user.status,
        createdAt=user.created_at,
        updatedAt=user.updated_at,
        deletedAt=user.deleted_at,
    )

def to_user_system_setting_response(setting: UserSystemSetting) -> UserSystemSettingResponse:
    """
    将用户系统设置 ORM 转为启动模块响应。

    :param setting: 用户系统设置实体。
    :return: ``UserSystemSettingResponse``。
    """
    return UserSystemSettingResponse(
        serverId=setting.server_id,
        clientId=setting.client_id,
        userId=setting.user_id,
        setting=parse_user_system_setting_json(setting.setting_json),
        createdAt=setting.created_at,
        updatedAt=setting.updated_at,
        deletedAt=setting.deleted_at,
    )

def to_user_game_setting_response(setting: UserGameSettingRead) -> UserGameSettingResponse:
    """
    将用户游戏设置读模型转为启动模块响应。

    :param setting: 游戏设置读模型。
    :return: ``UserGameSettingResponse``。
    """
    return UserGameSettingResponse(
        serverId=setting.server_id,
        clientId=setting.client_id,
        userId=setting.user_id,
        gameCode=setting.game_code,
        setting=setting.setting if setting.setting is not None else {},
        createdAt=setting.created_at,
        updatedAt=setting.updated_at,
        deletedAt=setting.deleted_at,
    )
