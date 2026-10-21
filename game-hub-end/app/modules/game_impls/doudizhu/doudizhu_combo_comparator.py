"""斗地主牌型大小比较。"""

from typing import Optional

from app.modules.game_impls.doudizhu.schemas import DoudizhuComboInfo

def can_beat(
    challenger: DoudizhuComboInfo,
    target: Optional[DoudizhuComboInfo],
) -> bool:
    """
    判断挑战方牌型是否能压过目标牌型。

    :param challenger: 挑战方牌型。
    :param target: 目标牌型；为空表示首家出牌。
    :return: 能压过为 ``True``。
    """
    if target is None:
        return True
    if challenger.isRocket:
        return True
    if target.isRocket:
        return False
    if challenger.isBomb and not target.isBomb:
        return True
    if not challenger.isBomb and target.isBomb:
        return False
    if challenger.isBomb and target.isBomb:
        return challenger.mainRankValue > target.mainRankValue
    if (
        challenger.comboType != target.comboType
        or challenger.cardCount != target.cardCount
        or challenger.chainLength != target.chainLength
    ):
        return False
    return challenger.mainRankValue > target.mainRankValue
