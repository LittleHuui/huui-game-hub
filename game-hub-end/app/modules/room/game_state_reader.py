"""房间对局运行时读取端口。"""

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.redis.redis_errors import RedisOperationError
from app.modules.room.consistent_game_state import ConsistentGameState
from app.modules.room.repository import RoomRepository
from app.modules.room.runtime_snapshot_codec import RuntimeSnapshotCodec, runtime_snapshot_codec
from app.modules.room.task_errors import (
    TaskObsoleteError,
    TaskObsoleteReason,
    TaskTemporaryInfrastructureError,
    TaskTemporaryReason,
)
from app.modules.strategy_turn.schemas import RuntimeSnapshot


class RetryableGameStateInconsistentException(BizException):
    """运行时快照与对局版本不一致，可重试。"""

    def __init__(self, message: str = "对局状态读取不一致，请重试") -> None:
        """初始化可重试不一致异常。"""
        super().__init__(ErrorCode.SYSTEM_ERROR, message=message)


class GameRuntimeNotFoundException(BizException):
    """权威检查确认房间运行时不存在。"""

    def __init__(self, message: str = "对局运行时不存在") -> None:
        """初始化运行时不存在异常。"""
        super().__init__(ErrorCode.PARAM_ERROR, message=message)


class GameStateReader(object):
    """从 Redis 读取策略回合运行时快照。"""

    def __init__(
        self,
        repository: RoomRepository,
        codec: RuntimeSnapshotCodec = runtime_snapshot_codec,
    ) -> None:
        """初始化统一快照读取器。"""
        self._repository = repository
        self._codec = codec

    async def load_consistent(self, room_id: str, max_retry: int = 3) -> ConsistentGameState:
        """
        读取版本一致的运行时快照与对局版本。

        :param room_id: 房间 ID。
        :param max_retry: 最大重试次数。
        :return: 一致对局状态。
        :raises RetryableGameStateInconsistentException: 重试耗尽仍不一致。
        :raises BizException: 对局尚未开始。
        """
        normalized_room_id = str(room_id or "").strip()
        retry_count = max(1, int(max_retry))
        for _index in range(retry_count):
            game_version_before = await self._repository.get_game_version(normalized_room_id)
            if game_version_before is None:
                raise GameRuntimeNotFoundException()
            runtime_data = await self._repository.get_runtime(normalized_room_id)
            if runtime_data is None:
                raise GameRuntimeNotFoundException()
            game_version_after = await self._repository.get_game_version(normalized_room_id)
            if game_version_after is None:
                raise GameRuntimeNotFoundException()
            if int(game_version_before) != int(game_version_after):
                continue
            snapshot = self._codec.decode(runtime_data)
            commit_version = int(snapshot.commitVersion or 0)
            if commit_version != int(game_version_after):
                continue
            return ConsistentGameState(
                snapshot=snapshot,
                gameVersion=int(game_version_after),
            )
        raise RetryableGameStateInconsistentException()

    async def load_consistent_for_task(self, room_id: str, max_retry: int = 3) -> ConsistentGameState:
        """
        任务路径读取版本一致的运行时快照；基础设施失败抛临时异常，运行时不存在抛过期异常。

        :param room_id: 房间 ID。
        :param max_retry: 最大重试次数。
        :return: 一致对局状态。
        :raises TaskTemporaryInfrastructureError: 读取暂时失败。
        :raises TaskObsoleteError: 权威运行时不存在。
        """
        normalized_room_id = str(room_id or "").strip()
        retry_count = max(1, int(max_retry))
        try:
            for _index in range(retry_count):
                game_version_before = await self._repository.get_game_version_for_task(
                    normalized_room_id,
                )
                if game_version_before is None:
                    raise TaskObsoleteError(TaskObsoleteReason.RUNTIME_MISSING)
                runtime_data = await self._repository.get_runtime_for_task(normalized_room_id)
                if runtime_data is None:
                    raise TaskObsoleteError(TaskObsoleteReason.RUNTIME_MISSING)
                game_version_after = await self._repository.get_game_version_for_task(
                    normalized_room_id,
                )
                if game_version_after is None:
                    raise TaskObsoleteError(TaskObsoleteReason.RUNTIME_MISSING)
                if int(game_version_before) != int(game_version_after):
                    continue
                snapshot = self._codec.decode(runtime_data)
                commit_version = int(snapshot.commitVersion or 0)
                if commit_version != int(game_version_after):
                    continue
                return ConsistentGameState(
                    snapshot=snapshot,
                    gameVersion=int(game_version_after),
                )
        except TaskObsoleteError:
            raise
        except TaskTemporaryInfrastructureError:
            raise
        except RedisOperationError as exc:
            raise TaskTemporaryInfrastructureError(TaskTemporaryReason.REDIS_UNAVAILABLE, cause=exc)
        except RetryableGameStateInconsistentException:
            raise TaskTemporaryInfrastructureError(TaskTemporaryReason.STATE_READER_RETRY)
        raise TaskTemporaryInfrastructureError(TaskTemporaryReason.STATE_READER_RETRY)
