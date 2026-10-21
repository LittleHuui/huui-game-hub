"""房间成员判定与查找工具。"""

from typing import Any, Dict, List, Optional


def find_member(
    members: List[Dict[str, Any]],
    player_id: str,
) -> Optional[Dict[str, Any]]:
    """
    在成员列表中查找指定玩家。

    :param members: 成员列表。
    :param player_id: 玩家 ID。
    :return: 成员对象；未找到时返回 ``None``。
    """
    for member in members:
        if member.get("playerId") == player_id:
            return member
    return None


def is_shell_managed(member: Dict[str, Any]) -> bool:
    """
    判断成员是否处于空壳托管状态。

    :param member: 成员对象。
    :return: 是否为空壳托管。
    """
    if not bool(member.get("isManaged")):
        return False
    return str(member.get("managedMode", "")).strip() == "shell"


def is_real_human_member(member: Dict[str, Any]) -> bool:
    """
    判断成员是否为真人真实成员（非 shell、非 AI）。

    :param member: 成员对象。
    :return: 是否为真人真实成员。
    """
    if is_shell_managed(member):
        return False
    return not bool(member.get("isAi"))


def has_real_human_member(members: List[Dict[str, Any]]) -> bool:
    """
    判断成员列表中是否仍有真人真实成员。

    :param members: 成员列表。
    :return: 是否存在真人真实成员。
    """
    for member in members:
        if is_real_human_member(member):
            return True
    return False


def sort_members_by_joined_at(members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按加入时间升序排列成员列表。

    :param members: 成员列表。
    :return: 排序后的新列表。
    """
    return sorted(members, key=lambda item: int(item.get("joinedAt", 0)))
