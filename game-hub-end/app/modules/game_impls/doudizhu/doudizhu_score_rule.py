"""斗地主积分理论结算规则。

本模块仅生成对局内 ``settlement`` 快照（理论零和）。
平台实际积分落库由 Room 层 ``GameSettlementService`` 负责。
"""

from typing import Dict, List, Optional

from app.common.exceptions import ValidationException
from app.modules.game_impls.doudizhu.doudizhu_constants import DOUDIZHU_PLAYER_COUNT
from app.modules.game_impls.doudizhu.schemas import (
    DoudizhuPlayerSettlement,
    DoudizhuSettlementResult,
)

_ROLE_LANDLORD = "landlord"
_ROLE_FARMER = "farmer"
_WINNER_LANDLORD = "landlord"
_WINNER_FARMER = "farmer"


class DoudizhuScoreInput(object):
    """斗地主结算输入参数。"""

    def __init__(
        self,
        player_ids: List[str],
        landlord_player_id: str,
        winner_role: str,
        personal_multipliers: Dict[str, int],
        global_multiplier: int,
        base_score: int,
        spring_type: Optional[str] = None,
        multiplier_details: Optional[Dict[str, object]] = None,
    ) -> None:
        """
        初始化结算输入。

        :param player_ids: 玩家 ID 列表，必须为 3 人。
        :param landlord_player_id: 地主玩家 ID。
        :param winner_role: 胜方角色 ``landlord`` / ``farmer``。
        :param personal_multipliers: 各玩家个人倍数。
        :param global_multiplier: 全局倍数。
        :param base_score: 底分。
        :param spring_type: 春天类型。
        :param multiplier_details: 倍数明细。
        """
        self.playerIds = player_ids
        self.landlordPlayerId = landlord_player_id
        self.winnerRole = winner_role
        self.personalMultipliers = personal_multipliers
        self.globalMultiplier = global_multiplier
        self.baseScore = base_score
        self.springType = spring_type
        self.multiplierDetails = multiplier_details or {}


def build_settlement(score_input: DoudizhuScoreInput) -> DoudizhuSettlementResult:
    """
    生成斗地主理论零和结算。

    :param score_input: 结算输入。
    :return: 结算结果。
    :raises ValidationException: 参数不合法时抛出。
    """
    _validate_score_input(score_input)
    theoretical = _build_theoretical_deltas(score_input)
    settlements = []
    for player_id in score_input.playerIds:
        role = (
            _ROLE_LANDLORD
            if player_id == score_input.landlordPlayerId
            else _ROLE_FARMER
        )
        score_delta = theoretical[player_id]
        settlements.append(
            DoudizhuPlayerSettlement(
                playerId=player_id,
                role=role,
                personalMultiplier=score_input.personalMultipliers[player_id],
                scoreDelta=score_delta,
            )
        )
    return DoudizhuSettlementResult(
        landlordPlayerId=score_input.landlordPlayerId,
        winnerRole=score_input.winnerRole,
        baseScore=score_input.baseScore,
        globalMultiplier=score_input.globalMultiplier,
        springType=score_input.springType,
        multiplierDetails=score_input.multiplierDetails,
        playerSettlements=settlements,
    )


def _validate_score_input(score_input: DoudizhuScoreInput) -> None:
    """
    校验结算输入参数。

    :param score_input: 结算输入。
    :raises ValidationException: 参数不合法时抛出。
    """
    if len(score_input.playerIds) != DOUDIZHU_PLAYER_COUNT:
        raise ValidationException(
            "斗地主结算要求 {0} 名玩家，当前为 {1}".format(
                DOUDIZHU_PLAYER_COUNT,
                len(score_input.playerIds),
            )
        )
    if score_input.landlordPlayerId not in score_input.playerIds:
        raise ValidationException("地主玩家不在玩家列表中")
    if score_input.winnerRole not in (_WINNER_LANDLORD, _WINNER_FARMER):
        raise ValidationException("胜方角色必须为 landlord 或 farmer")
    if score_input.baseScore < 1:
        raise ValidationException("底分必须大于 0")
    if score_input.globalMultiplier < 1:
        raise ValidationException("全局倍数必须大于 0")
    for player_id in score_input.playerIds:
        multiplier = score_input.personalMultipliers.get(player_id)
        if multiplier is None or multiplier < 1:
            raise ValidationException(
                "玩家 {0} 个人倍数无效".format(player_id)
            )


def _build_theoretical_deltas(
    score_input: DoudizhuScoreInput,
) -> Dict[str, int]:
    """
    按地主与每名农民的独立结算关系计算理论积分变动（零和）。

    单对结算额：
    baseScore × globalMultiplier × landlordPersonalMultiplier × farmerPersonalMultiplier

    :param score_input: 结算输入。
    :return: 玩家 ID -> 理论积分变动。
    """
    farmers = [
        player_id
        for player_id in score_input.playerIds
        if player_id != score_input.landlordPlayerId
    ]
    landlord_id = score_input.landlordPlayerId
    landlord_multiplier = score_input.personalMultipliers[landlord_id]
    base_unit = score_input.baseScore * score_input.globalMultiplier
    deltas = {}  # type: Dict[str, int]
    pair_amounts = []
    for farmer_id in farmers:
        farmer_multiplier = score_input.personalMultipliers[farmer_id]
        pair_amount = base_unit * landlord_multiplier * farmer_multiplier
        pair_amounts.append(pair_amount)

    if score_input.winnerRole == _WINNER_LANDLORD:
        landlord_gain = 0
        for farmer_id, pair_amount in zip(farmers, pair_amounts):
            deltas[farmer_id] = -pair_amount
            landlord_gain += pair_amount
        deltas[landlord_id] = landlord_gain
    else:
        landlord_loss = 0
        for farmer_id, pair_amount in zip(farmers, pair_amounts):
            deltas[farmer_id] = pair_amount
            landlord_loss += pair_amount
        deltas[landlord_id] = -landlord_loss

    total = sum(deltas.values())
    if total != 0:
        raise ValidationException("理论结算未满足零和约束")
    return deltas
