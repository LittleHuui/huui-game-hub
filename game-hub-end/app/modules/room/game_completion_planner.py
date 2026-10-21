"""对局结束纯规划器。"""

import copy
from typing import Any, Dict, List, Optional

from app.core.id_utils import generate_server_id
from app.modules.room.game_completion_schemas import (
    TERMINAL_DISPLAY_MS,
    GameCompletionPlan,
    OwnerTransferPlan,
)
from app.modules.room.room_member_support import (
    find_member,
    has_real_human_member,
    is_real_human_member,
    is_shell_managed,
    sort_members_by_joined_at,
)
from app.modules.strategy_turn.schemas import RuntimeSnapshot
from app.modules.strategy_turn.terminal_schemas import (
    TerminalMetadata,
    TerminalOwnerTransferPlan,
)


class GameCompletionPlanner(object):
    """根据终局快照与成员状态生成终局提交计划，不访问 Redis。"""

    def build_plan(
        self,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        final_snapshot: RuntimeSnapshot,
        committed_at: int,
    ) -> GameCompletionPlan:
        """
        生成终局原子提交计划。

        :param meta: 当前房间元信息。
        :param members: 当前房间全部成员列表。
        :param final_snapshot: 生命周期产出的终局快照。
        :param committed_at: 提交时间戳（毫秒）。
        :return: 终局计划。
        """
        next_meta = copy.deepcopy(meta if isinstance(meta, dict) else {})
        next_meta["status"] = "playing"
        next_meta["updatedAt"] = int(committed_at)

        active_members = [
            member for member in members if not is_shell_managed(member)
        ]
        dissolve_after_terminal = not has_real_human_member(active_members)

        owner_transfer = self._build_owner_transfer_plan(next_meta, active_members)
        if owner_transfer is not None:
            next_meta["ownerPlayerId"] = owner_transfer.ownerPlayerId
            next_meta["ownerNickname"] = owner_transfer.ownerNickname

        members_to_remove = self._collect_stale_member_ids(members, active_members)
        directive = final_snapshot.terminalDirective
        settlement_required = bool(
            directive is not None and directive.requiresPlatformSettlement,
        )
        terminal_status = "PENDING_SETTLEMENT" if settlement_required else "DISPLAYING"
        display_duration_ms = TERMINAL_DISPLAY_MS
        if directive is not None:
            display_duration_ms = int(directive.displayDurationMs or TERMINAL_DISPLAY_MS)
        display_until = int(committed_at)
        if not settlement_required:
            display_until = int(committed_at) + display_duration_ms
        if dissolve_after_terminal:
            display_until = int(committed_at)

        settlement_id = generate_server_id("settlement") if settlement_required else None
        owner_transfer_plan = None
        if owner_transfer is not None:
            owner_transfer_plan = TerminalOwnerTransferPlan(
                ownerPlayerId=owner_transfer.ownerPlayerId,
                ownerNickname=owner_transfer.ownerNickname,
            )
        terminal_metadata = TerminalMetadata(
            terminalStatus=terminal_status,
            settlementId=settlement_id,
            settlementStatus="PENDING" if settlement_required else None,
            settlementResultId=None,
            terminalDisplayUntil=display_until,
            dissolveAfterTerminal=bool(dissolve_after_terminal),
            membersToRemoveAfterTerminal=list(members_to_remove),
            ownerTransferPlan=owner_transfer_plan,
        )
        terminal_snapshot = final_snapshot.model_copy(
            update={
                "isGameOver": True,
                "terminalMetadata": terminal_metadata,
                "updatedAt": int(committed_at),
            },
        )
        return GameCompletionPlan(
            terminalSnapshot=terminal_snapshot,
            nextRoomMeta=next_meta,
            dissolveAfterTerminal=bool(dissolve_after_terminal),
            membersToRemoveAfterTerminal=members_to_remove,
            ownerTransferPlan=owner_transfer,
            terminalDisplayUntil=display_until,
            settlementRequired=bool(settlement_required),
        )

    def _build_owner_transfer_plan(
        self,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
    ) -> Optional[OwnerTransferPlan]:
        """
        计算终局后房主转移计划。

        :param meta: 房间元信息。
        :param members: 活跃成员列表。
        :return: 房主转移计划；无需转移时返回 ``None``。
        """
        owner_player_id = str(meta.get("ownerPlayerId", "")).strip()
        owner_member = find_member(members, owner_player_id)
        if owner_member is not None and is_real_human_member(owner_member):
            return None
        human_members = [
            item for item in sort_members_by_joined_at(members)
            if is_real_human_member(item)
        ]
        if not human_members:
            return None
        new_owner = human_members[0]
        new_owner_id = str(new_owner.get("playerId", "")).strip()
        new_owner_nickname = str(new_owner.get("nickname", new_owner_id)).strip()
        if not new_owner_nickname:
            new_owner_nickname = new_owner_id
        return OwnerTransferPlan(
            ownerPlayerId=new_owner_id,
            ownerNickname=new_owner_nickname,
        )

    def _collect_stale_member_ids(
        self,
        all_members: List[Dict[str, Any]],
        active_members: List[Dict[str, Any]],
    ) -> List[str]:
        """
        收集终局 finalize 时需清理的过期成员 ID。

        :param all_members: Redis 中全部成员。
        :param active_members: 非 shell 的活跃成员。
        :return: 待移除成员 ID 列表。
        """
        active_ids = set()
        for member in active_members:
            player_id = str(member.get("playerId", "")).strip()
            if player_id:
                active_ids.add(player_id)
        stale_ids = []
        for member in all_members:
            player_id = str(member.get("playerId", "")).strip()
            if player_id and player_id not in active_ids:
                stale_ids.append(player_id)
        return stale_ids
