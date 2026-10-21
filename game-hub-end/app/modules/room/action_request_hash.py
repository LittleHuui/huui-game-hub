"""房间动作请求稳定摘要计算。"""

import hashlib
import json
from typing import Any, Dict

from app.modules.strategy_turn.schemas import ActionSubmission


def build_action_request_hash(
    room_id: str,
    player_id: str,
    base_version: int,
    submission: ActionSubmission,
) -> str:
    """
    按稳定字段排序后计算动作请求摘要。

    :param room_id: 房间 ID。
    :param player_id: 玩家 ID。
    :param base_version: 客户端已知对局版本号。
    :param submission: 动作提交意图。
    :return: 十六进制 SHA256 摘要。
    """
    payload = _build_request_payload(room_id, player_id, base_version, submission)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_request_payload(
    room_id: str,
    player_id: str,
    base_version: int,
    submission: ActionSubmission,
) -> Dict[str, Any]:
    """
    构造请求摘要输入对象。

    :param room_id: 房间 ID。
    :param player_id: 玩家 ID。
    :param base_version: 客户端已知对局版本号。
    :param submission: 动作提交意图。
    :return: 可序列化摘要对象。
    """
    action_type = str(submission.actionType or "").strip()
    input_payload = submission.input.model_dump()
    return {
        "roomId": str(room_id or "").strip(),
        "playerId": str(player_id or "").strip(),
        "baseVersion": int(base_version),
        "actionType": action_type,
        "input": input_payload,
    }
