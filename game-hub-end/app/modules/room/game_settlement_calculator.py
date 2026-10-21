"""平台积分结算纯计算（无 I/O）。"""

from typing import Dict, List, Optional, Tuple

from app.modules.room.game_settlement_schemas import PlayerSettlementResult
from app.modules.strategy_turn.schemas import TheoreticalPlayerSettlement


def compute_platform_player_settlements(
    theoretical_players: List[TheoreticalPlayerSettlement],
    player_ai_map: Dict[str, bool],
    balance_by_player: Dict[str, int],
) -> Tuple[List[PlayerSettlementResult], int]:
    """
    根据理论零和结算与钱包余额计算平台实际结算。

    规则：输家余额不低于 0；赢家获得完整 expectedDelta；差额由系统补差；AI 不走钱包。

    :param theoretical_players: 理论玩家结算列表。
    :param player_ai_map: 玩家 ID -> 是否 AI。
    :param balance_by_player: 真人玩家结算前余额。
    :return: ``(玩家结算列表, systemDelta)``。
    """
    human_losers = []
    human_winners = []
    zero_humans = []
    ai_entries = []
    for item in theoretical_players or []:
        player_id = str(item.playerId or "").strip()
        if not player_id:
            continue
        expected_delta = int(item.expectedDelta)
        if bool(player_ai_map.get(player_id, False)):
            ai_entries.append((player_id, expected_delta))
            continue
        if expected_delta < 0:
            human_losers.append((player_id, expected_delta))
        elif expected_delta > 0:
            human_winners.append((player_id, expected_delta))
        else:
            zero_humans.append((player_id, expected_delta))

    results = []
    total_loser_payment = 0
    for player_id, expected_delta in human_losers:
        balance_before = max(0, int(balance_by_player.get(player_id, 0)))
        pay_amount = min(abs(expected_delta), balance_before)
        actual_delta = -pay_amount
        insufficient_amount = abs(expected_delta) - pay_amount
        balance_after = balance_before + actual_delta
        total_loser_payment += pay_amount
        results.append(
            PlayerSettlementResult(
                playerId=player_id,
                expectedDelta=expected_delta,
                actualDelta=actual_delta,
                balanceBefore=balance_before,
                balanceAfter=balance_after,
                insufficientAmount=insufficient_amount,
            ),
        )

    for player_id, expected_delta in human_winners:
        balance_before = max(0, int(balance_by_player.get(player_id, 0)))
        actual_delta = expected_delta
        balance_after = balance_before + actual_delta
        results.append(
            PlayerSettlementResult(
                playerId=player_id,
                expectedDelta=expected_delta,
                actualDelta=actual_delta,
                balanceBefore=balance_before,
                balanceAfter=balance_after,
                insufficientAmount=0,
            ),
        )

    for player_id, expected_delta in zero_humans:
        balance_before = max(0, int(balance_by_player.get(player_id, 0)))
        results.append(
            PlayerSettlementResult(
                playerId=player_id,
                expectedDelta=0,
                actualDelta=0,
                balanceBefore=balance_before,
                balanceAfter=balance_before,
                insufficientAmount=0,
            ),
        )

    for player_id, expected_delta in ai_entries:
        results.append(
            PlayerSettlementResult(
                playerId=player_id,
                expectedDelta=expected_delta,
                actualDelta=0,
                balanceBefore=0,
                balanceAfter=0,
                insufficientAmount=0,
                isAi=True,
            ),
        )

    total_winner_gain = sum(
        item.actualDelta for item in results if item.actualDelta > 0
    )
    system_delta = int(total_winner_gain) - int(total_loser_payment)
    return results, system_delta


def validate_theoretical_zero_sum(
    theoretical_players: List[TheoreticalPlayerSettlement],
) -> Optional[str]:
    """
    校验理论结算是否零和。

    :param theoretical_players: 理论玩家结算列表。
    :return: 错误原因；合法时返回 ``None``。
    """
    total = 0
    for item in theoretical_players or []:
        total += int(item.expectedDelta)
    if total != 0:
        return "理论结算不满足零和约束"
    return None
