"""Redis key 集中定义。"""

import zlib
from typing import List



class RedisKeys(object):
    """平台 Redis key 生成器。"""

    ROOM_SHARD_COUNT = 64

    @staticmethod
    def room_shard(room_id: str) -> int:
        """返回房间的稳定 Redis 分片编号。"""
        normalized_room_id = str(room_id or "").strip()
        return int(zlib.crc32(normalized_room_id.encode("utf-8")) & 0xFFFFFFFF) % RedisKeys.ROOM_SHARD_COUNT

    @staticmethod
    def _room_shard_tag(room_id: str) -> str:
        """生成房间所属分片的 Redis Cluster hash tag。"""
        return "room-shard:{0}".format(RedisKeys.room_shard(room_id))

    @staticmethod
    def _shard_tagged(shard_index: int, suffix: str) -> str:
        """Return a key placed in the requested room shard."""
        normalized_index = int(shard_index) % RedisKeys.ROOM_SHARD_COUNT
        return "game-hub:{{room-shard:{0}}}:{1}".format(
            normalized_index,
            str(suffix or "").strip(),
        )

    @staticmethod
    def _room_tagged(room_id: str, suffix: str) -> str:
        """
        生成带 hash tag 的房间级 Redis key，保证同房间数据位于同一槽位。

        :param room_id: 房间 ID。
        :param suffix: key 后缀。
        :return: Redis key。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_suffix = str(suffix or "").strip()
        return "game-hub:{{{0}}}:room:{1}:{2}".format(
            RedisKeys._room_shard_tag(normalized_room_id),
            normalized_room_id,
            normalized_suffix,
        )

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
    def auth_realtime_ticket(ticket: str) -> str:
        """
        Generate a short-lived realtime authentication ticket key.
        :param ticket: Opaque ticket value.
        :return: Redis key.
        """
        return "auth:realtime-ticket:{0}".format(str(ticket or "").strip())

    @staticmethod
    def room_meta(room_id: str) -> str:
        """
        生成房间元信息 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "meta")

    @staticmethod
    def room_meta_pattern() -> str:
        """生成全部房间 meta 的扫描 pattern。"""
        return "game-hub:{room-shard:*}:room:*:meta"

    @staticmethod
    def room_players(room_id: str) -> str:
        """
        生成房间玩家 hash key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "players")

    @staticmethod
    def room_runtime(room_id: str) -> str:
        """
        生成房间运行期 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "runtime")

    @staticmethod
    def room_events(room_id: str) -> str:
        """
        生成房间事件 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "events")

    @staticmethod
    def room_presence(room_id: str) -> str:
        """
        生成房间探活状态 hash key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "presence")

    @staticmethod
    def room_room_version(room_id: str) -> str:
        """
        生成房间元数据版本号 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "room-version")

    @staticmethod
    def room_game_version(room_id: str) -> str:
        """
        生成对局运行时版本号 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "game-version")

    @staticmethod
    def room_lock(room_id: str) -> str:
        """
        生成房间分布式锁 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "lock")

    @staticmethod
    def room_action_request(room_id: str, player_id: str, request_id: str) -> str:
        """
        生成单条动作请求幂等记录 key。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request_id: 请求 ID。
        :return: Redis key。
        """
        normalized_player_id = str(player_id or "").strip()
        normalized_request_id = str(request_id or "").strip()
        return RedisKeys._room_tagged(
            room_id,
            "request:{0}:{1}".format(normalized_player_id, normalized_request_id),
        )

    @staticmethod
    def room_outbox_records(room_id: str) -> str:
        """
        生成房间 Outbox 记录 Hash key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "outbox:records")

    @staticmethod
    def room_outbox_records_pattern() -> str:
        """
        生成全部房间 Outbox records Hash 的 SCAN pattern。

        :return: Redis scan pattern。
        """
        return "game-hub:{room-shard:*}:room:*:outbox:records"

    @staticmethod
    def room_outbox_due(room_id: str) -> str:
        """
        生成房间 Outbox 到期 ZSet key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "outbox:due")

    @staticmethod
    def room_outbox_dedupe(room_id: str) -> str:
        """
        生成房间 Outbox 去重 Hash key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "outbox:dedupe")

    @staticmethod
    def room_outbox_dispatch_lease(room_id: str) -> str:
        """生成房间 Outbox 分发权租约 key。"""
        return RedisKeys._room_tagged(room_id, "outbox:dispatch-lease")

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
    def managed_task_records(room_id: str) -> str:
        """
        生成托管任务到期 sorted set key。

        :return: Redis key。
        """
        return RedisKeys.managed_task_records_shard(RedisKeys.room_shard(room_id))

    @staticmethod
    def managed_task_records_shard(shard_index: int) -> str:
        """
        生成托管任务执行中 sorted set key。

        :return: Redis key。
        """
        return RedisKeys._shard_tagged(shard_index, "managed-task:records")

    @staticmethod
    def managed_task_due(room_id: str) -> str:
        """
        生成托管任务数据 key。

        :param task_id: 任务 ID。
        :return: Redis key。
        """
        return RedisKeys.managed_task_due_shard(RedisKeys.room_shard(room_id))

    @staticmethod
    def managed_task_due_shard(shard_index: int) -> str:
        """
        生成托管任务房间执行锁 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._shard_tagged(shard_index, "managed-task:due")

    @staticmethod
    def managed_task_processing(room_id: str) -> str:
        return RedisKeys.managed_task_processing_shard(RedisKeys.room_shard(room_id))

    @staticmethod
    def managed_task_processing_shard(shard_index: int) -> str:
        return RedisKeys._shard_tagged(shard_index, "managed-task:processing")

    @staticmethod
    def managed_task_room_running(room_id: str) -> str:
        return RedisKeys._room_tagged(room_id, "managed-task:room-running")

    @staticmethod
    def managed_task_dedupe(
        room_id: str,
        player_id: str,
        expected_version: int,
        expected_phase: str = "",
    ) -> str:
        """
        生成托管任务去重 key。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param expected_version: 期望对局版本。
        :param expected_phase: 期望阶段。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "managed-task:dedupe:{0}:{1}:{2}".format(
            player_id,
            int(expected_version),
            str(expected_phase or "").strip() or "unknown",
        ))

    @staticmethod
    def auto_advance_task_records(room_id: str) -> str:
        """
        生成房间自动推进任务到期 sorted set key。

        :return: Redis key。
        """
        return RedisKeys.auto_advance_task_records_shard(RedisKeys.room_shard(room_id))

    @staticmethod
    def auto_advance_task_records_shard(shard_index: int) -> str:
        """
        生成房间自动推进任务执行中 sorted set key。

        :return: Redis key。
        """
        return RedisKeys._shard_tagged(shard_index, "auto-advance-task:records")

    @staticmethod
    def auto_advance_task_due(room_id: str) -> str:
        """
        生成房间自动推进任务数据 key。

        :param task_id: 任务 ID。
        :return: Redis key。
        """
        return RedisKeys.auto_advance_task_due_shard(RedisKeys.room_shard(room_id))

    @staticmethod
    def auto_advance_task_due_shard(shard_index: int) -> str:
        """
        生成房间自动推进任务房间执行锁 key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return RedisKeys._shard_tagged(shard_index, "auto-advance-task:due")

    @staticmethod
    def auto_advance_task_processing(room_id: str) -> str:
        return RedisKeys.auto_advance_task_processing_shard(RedisKeys.room_shard(room_id))

    @staticmethod
    def auto_advance_task_processing_shard(shard_index: int) -> str:
        return RedisKeys._shard_tagged(shard_index, "auto-advance-task:processing")

    @staticmethod
    def auto_advance_task_room_running(room_id: str) -> str:
        return RedisKeys._room_tagged(room_id, "auto-advance-task:room-running")

    @staticmethod
    def outbox_ready_rooms(room_id: str) -> str:
        """
        生成房间所属分片的 Outbox 就绪房间 ZSet key。

        :param room_id: 房间 ID。
        :return: Redis key。
        """
        return "game-hub:{{{0}}}:post-turn-outbox:ready-rooms".format(
            RedisKeys._room_shard_tag(room_id),
        )

    @staticmethod
    def outbox_ready_room_shards() -> List[str]:
        """返回全部 Outbox 就绪分片 ZSet key。"""
        return [
            "game-hub:{{room-shard:{0}}}:post-turn-outbox:ready-rooms".format(index)
            for index in range(RedisKeys.ROOM_SHARD_COUNT)
        ]

    @staticmethod
    def websocket_connection(service_id: str) -> str:
        """
        生成单个用户 WebSocket 活跃连接登记 key。
        :param service_id: 用户服务端 ID。
        :return: Redis key。
        """
        return "game-hub:websocket:connection:{0}".format(str(service_id or "").strip())

    @staticmethod
    def websocket_events() -> str:
        """
        生成 WebSocket 跨进程投递频道。
        :return: Redis channel。
        """
        return "game-hub:websocket:events"

    @staticmethod
    def auto_advance_task_dedupe(room_id: str, expected_version: int, expected_phase: str) -> str:
        """
        生成房间自动推进任务去重 key。

        :param room_id: 房间 ID。
        :param expected_version: 期望对局版本。
        :param expected_phase: 期望阶段标识。
        :return: Redis key。
        """
        return RedisKeys._room_tagged(room_id, "auto-advance-task:dedupe:{0}:{1}".format(
            int(expected_version),
            expected_phase,
        ))
