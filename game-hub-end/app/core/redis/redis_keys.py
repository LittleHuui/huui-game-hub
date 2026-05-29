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

    @staticmethod
    def room_meta(room_id: str) -> str:
        """
        生成房间元信息 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:meta".format(room_id)

    @staticmethod
    def room_players(room_id: str) -> str:
        """
        生成房间玩家 hash key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:players".format(room_id)

    @staticmethod
    def room_runtime(room_id: str) -> str:
        """
        生成房间运行期 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:runtime".format(room_id)

    @staticmethod
    def room_public_state(room_id: str) -> str:
        """
        生成房间公开状态 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:public-state".format(room_id)

    @staticmethod
    def room_private_state(room_id: str, player_id: str) -> str:
        """
        生成房间玩家私有状态 key。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:private-state:{1}".format(room_id, player_id)

    @staticmethod
    def room_private_state_pattern(room_id: str) -> str:
        """
        生成房间玩家私有状态扫描 pattern。

        :param room_id: 房间 ID。
        :return: Redis scan pattern。
        """
        return "game-hub:room:{0}:private-state:*".format(room_id)

    @staticmethod
    def room_legal_actions(room_id: str, player_id: str) -> str:
        """
        生成房间玩家合法动作 key。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:legal-actions:{1}".format(room_id, player_id)

    @staticmethod
    def room_legal_actions_pattern(room_id: str) -> str:
        """
        生成房间玩家合法动作扫描 pattern。

        :param room_id: 房间 ID。
        :return: Redis scan pattern。
        """
        return "game-hub:room:{0}:legal-actions:*".format(room_id)

    @staticmethod
    def room_events(room_id: str) -> str:
        """
        生成房间事件 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:events".format(room_id)

    @staticmethod
    def room_presence(room_id: str) -> str:
        """
        生成房间探活状态 hash key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:presence".format(room_id)

    @staticmethod
    def room_version(room_id: str) -> str:
        """
        生成房间版本号 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:version".format(room_id)

    @staticmethod
    def room_lock(room_id: str) -> str:
        """
        生成房间分布式锁 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:room:{0}:lock".format(room_id)

    @staticmethod
    def player_room(player_id: str) -> str:
        """
        生成玩家当前房间索引 key。

        :param player_id: 玩家 ID。
        :return: Redis key。
        """
        return "game-hub:player:{0}:room".format(player_id)

    @staticmethod
    def player_managed_shell_room(player_id: str, game_code: str) -> str:
        """
        生成玩家托管空壳房间索引 key。

        :param player_id: 玩家 ID。
        :param game_code: 游戏编码。
        :return: Redis key。
        """
        return "game-hub:player:{0}:managed-shell:{1}".format(player_id, game_code)

    @staticmethod
    def game_rooms(game_code: str) -> str:
        """
        生成按游戏编码索引的房间 ID 集合 key。

        :param game_code: 游戏编码。
        :return: Redis key。
        """
        return "game-hub:game:{0}:rooms".format(game_code)

    @staticmethod
    def playing_rooms() -> str:
        """
        生成对局中房间 ID 集合 key。

        :return: Redis key。
        """
        return "game-hub:rooms:playing"

    @staticmethod
    def managed_task_due() -> str:
        """
        生成托管任务到期 sorted set key。

        :return: Redis key。
        """
        return "game-hub:managed-task:due"

    @staticmethod
    def managed_task_processing() -> str:
        """
        生成托管任务执行中 sorted set key。

        :return: Redis key。
        """
        return "game-hub:managed-task:processing"

    @staticmethod
    def managed_task(task_id: str) -> str:
        """
        生成托管任务数据 key。

        :param task_id: 任务 ID。
        :return: Redis key。
        """
        return "game-hub:managed-task:{0}".format(task_id)

    @staticmethod
    def managed_task_room_running(room_id: str) -> str:
        """
        生成托管任务房间执行锁 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:managed-task:room-running:{0}".format(room_id)

    @staticmethod
    def managed_task_dedupe(room_id: str, player_id: str, expected_version: int) -> str:
        """
        生成托管任务去重 key。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param expected_version: 期望房间版本。
        :return: Redis key。
        """
        return "game-hub:managed-task:dedupe:{0}:{1}:{2}".format(
            room_id,
            player_id,
            int(expected_version),
        )
