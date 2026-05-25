"""Redis key 集中定义。"""


class RedisKeys(object):
    """平台 Redis key 生成器。"""

    @staticmethod
    def user_online(service_id: str) -> str:
        """
        生成在线用户状态 key。

        :param service_id: 用户服务端 ID。
        :return: Redis key。
        """
        return "game-hub:user:online:{0}".format(service_id)

    @staticmethod
    def user_online_pattern() -> str:
        """
        生成在线用户状态扫描 pattern。

        :return: Redis scan pattern。
        """
        return "game-hub:user:online:*"
