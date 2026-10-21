"""认证相关启动期配置校验。"""

from app.core.config import Settings


def validate_auth_settings(settings: Settings) -> None:
    """
    校验认证密钥配置；所有环境缺失时均阻止启动。

    :param settings: 应用配置。
    :return: 无。
    :raises RuntimeError: 未配置 ``AUTH_JWT_SECRET``。
    """
    secret = settings.AUTH_JWT_SECRET
    if secret is not None and str(secret).strip():
        return
    raise RuntimeError("生产环境必须配置 AUTH_JWT_SECRET")
