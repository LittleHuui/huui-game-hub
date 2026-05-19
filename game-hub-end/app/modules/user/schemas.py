"""用户域 Pydantic 模型。"""

import json
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.common.base_entity import BaseEntityResponse
from app.common.camel_schema import CAMEL_MODEL_CONFIG, camel_field
from app.modules.user.json_schemas import UserSystemSettingJson
from app.modules.user.models import UserAccount, UserDevice, UserGameSetting, UserSystemSetting


class UserAccountCreate(BaseModel):
    """创建用户账号请求体。"""

    model_config = CAMEL_MODEL_CONFIG

    clientId: str = camel_field("clientId", min_length=1, description="客户端幂等 ID")
    username: str = Field(min_length=1, description="全局唯一用户名")
    nickname: str = Field(min_length=1, description="展示昵称")
    avatar: Optional[str] = Field(default=None, description="头像地址")


class UserAccountUpdateNickname(BaseModel):
    """更新昵称请求体。"""

    model_config = ConfigDict(extra="forbid")

    nickname: str = Field(min_length=1, description="新的展示昵称")


class UserAccountRead(BaseModel):
    """用户账号响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    username: str
    nickname: str
    avatar: Optional[str] = None
    status: str
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class UserDeviceBind(BaseModel):
    """绑定或更新设备请求体（userId 由路径提供）。"""

    model_config = CAMEL_MODEL_CONFIG

    clientId: str = camel_field("clientId", min_length=1, description="该设备记录的客户端幂等 ID")
    deviceId: str = camel_field("deviceId", min_length=1, description="前端本地设备 ID")
    deviceName: Optional[str] = camel_field("deviceName", default=None, description="设备展示名")
    deviceType: Optional[str] = camel_field("deviceType", default=None, description="设备类型")


class UserDeviceRead(BaseModel):
    """用户设备响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    user_id: str
    device_id: str
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    last_login_at: Optional[int] = None
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class UserGameSettingRead(BaseModel):
    """用户游戏设置响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    user_id: str
    game_code: str
    setting: Optional[Dict[str, Any]] = None
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class UserGameSettingUpsert(BaseModel):
    """写入用户游戏设置请求体。"""

    model_config = ConfigDict(extra="forbid")

    setting: Optional[Dict[str, Any]] = Field(default=None, description="游戏个性化设置 JSON 对象")


class UserSystemSettingRead(BaseModel):
    """用户系统设置响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    user_id: str
    setting: UserSystemSettingJson
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class UserSystemSettingUpsert(BaseModel):
    """覆盖写入用户系统设置请求体。"""

    model_config = ConfigDict(extra="forbid")

    setting: UserSystemSettingJson = Field(description="平台级系统偏好设置")


class UserDetailRead(BaseModel):
    """用户详情：账号与设备列表。"""

    user: UserAccountRead
    devices: List[UserDeviceRead]


class UserAccountResponse(BaseEntityResponse):
    """用户账号 HTTP 响应（camelCase）。"""

    username: str
    nickname: str
    avatar: Optional[str] = None
    status: str


class UserDeviceResponse(BaseEntityResponse):
    """用户设备 HTTP 响应（camelCase）。"""

    userId: str
    deviceId: str
    deviceName: Optional[str] = None
    deviceType: Optional[str] = None
    lastLoginAt: Optional[int] = None


class UserGameSettingResponse(BaseEntityResponse):
    """用户游戏设置 HTTP 响应（camelCase）。"""

    userId: str
    gameCode: str
    setting: Dict[str, Any]


class UserSystemSettingResponse(BaseEntityResponse):
    """用户系统设置 HTTP 响应（camelCase）。"""

    userId: str
    setting: UserSystemSettingJson


class UserDetailResponse(BaseModel):
    """用户详情 HTTP 响应（camelCase）。"""

    model_config = ConfigDict(extra="forbid")

    user: UserAccountResponse
    devices: List[UserDeviceResponse]


def user_account_to_response(
    account: Union[UserAccount, UserAccountRead],
) -> UserAccountResponse:
    """
    将用户账号实体或读模型转为 HTTP 响应。

    :param account: ORM 或 ``UserAccountRead``。
    :return: ``UserAccountResponse``。
    """
    return UserAccountResponse(
        serverId=account.server_id,
        clientId=account.client_id,
        username=account.username,
        nickname=account.nickname,
        avatar=account.avatar,
        status=account.status,
        createdAt=account.created_at,
        updatedAt=account.updated_at,
        deletedAt=account.deleted_at,
    )


def user_device_to_response(
    device: Union[UserDevice, UserDeviceRead],
) -> UserDeviceResponse:
    """
    将用户设备实体或读模型转为 HTTP 响应。

    :param device: ORM 或 ``UserDeviceRead``。
    :return: ``UserDeviceResponse``。
    """
    return UserDeviceResponse(
        serverId=device.server_id,
        clientId=device.client_id,
        userId=device.user_id,
        deviceId=device.device_id,
        deviceName=device.device_name,
        deviceType=device.device_type,
        lastLoginAt=device.last_login_at,
        createdAt=device.created_at,
        updatedAt=device.updated_at,
        deletedAt=device.deleted_at,
    )


def user_game_setting_read_to_response(read: UserGameSettingRead) -> UserGameSettingResponse:
    """
    将用户游戏设置读模型转为 HTTP 响应。

    :param read: ``UserGameSettingRead``。
    :return: ``UserGameSettingResponse``。
    """
    return UserGameSettingResponse(
        serverId=read.server_id,
        clientId=read.client_id,
        userId=read.user_id,
        gameCode=read.game_code,
        setting=read.setting if read.setting is not None else {},
        createdAt=read.created_at,
        updatedAt=read.updated_at,
        deletedAt=read.deleted_at,
    )


def user_system_setting_read_to_response(read: UserSystemSettingRead) -> UserSystemSettingResponse:
    """
    将用户系统设置读模型转为 HTTP 响应。

    :param read: ``UserSystemSettingRead``。
    :return: ``UserSystemSettingResponse``。
    """
    return UserSystemSettingResponse(
        serverId=read.server_id,
        clientId=read.client_id,
        userId=read.user_id,
        setting=read.setting,
        createdAt=read.created_at,
        updatedAt=read.updated_at,
        deletedAt=read.deleted_at,
    )


def user_detail_to_response(detail: UserDetailRead) -> UserDetailResponse:
    """
    将用户详情读模型转为 HTTP 响应。

    :param detail: ``UserDetailRead``。
    :return: ``UserDetailResponse``。
    """
    return UserDetailResponse(
        user=user_account_to_response(detail.user),
        devices=[user_device_to_response(d) for d in detail.devices],
    )


def decode_setting_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    将数据库中的 setting_json 文本解析为字典。

    :param raw: 原始 JSON 文本，可为空。
    :return: 字典或 ``None``。
    """
    if raw is None or not raw.strip():
        return None
    return json.loads(raw)


def encode_setting_json(data: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    将设置字典序列化为存库字符串。

    :param data: 设置对象，可为空。
    :return: JSON 文本或 ``None``。
    """
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def encode_user_system_setting_json(data: UserSystemSettingJson) -> str:
    """
    将 ``UserSystemSettingJson`` 序列化为存库字符串。

    :param data: 系统设置对象。
    :return: JSON 文本。
    """
    return json.dumps(data.model_dump(), ensure_ascii=False, separators=(",", ":"))


def decode_user_system_setting_json(raw: str) -> UserSystemSettingJson:
    """
    将数据库中的 setting_json 文本解析为 ``UserSystemSettingJson``。

    :param raw: 原始 JSON 文本。
    :return: 解析后的设置对象。
    """
    return UserSystemSettingJson.model_validate_json(raw)


def user_system_setting_to_read(entity: UserSystemSetting) -> UserSystemSettingRead:
    """
    将 ``UserSystemSetting`` ORM 转为带解析后 ``setting`` 的读模型。

    :param entity: ORM 实例。
    :return: ``UserSystemSettingRead``。
    """
    return UserSystemSettingRead(
        server_id=entity.server_id,
        client_id=entity.client_id,
        user_id=entity.user_id,
        setting=decode_user_system_setting_json(entity.setting_json),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        deleted_at=entity.deleted_at,
    )


def user_game_setting_to_read(entity: UserGameSetting) -> UserGameSettingRead:
    """
    将 ``UserGameSetting`` ORM 转为带解析后 ``setting`` 的读模型。

    :param entity: ORM 实例。
    :return: ``UserGameSettingRead``。
    """
    return UserGameSettingRead(
        server_id=entity.server_id,
        client_id=entity.client_id,
        user_id=entity.user_id,
        game_code=entity.game_code,
        setting=decode_setting_json(entity.setting_json),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        deleted_at=entity.deleted_at,
    )
