"""经典斗地主叫分合法性规则，供交互与生命周期共同使用。"""

from typing import Any, Dict, List

from app.common.exceptions import ValidationException
from app.modules.game_impls.doudizhu.doudizhu_constants import PHASE_CALLING


BID_SCORES = (1, 2, 3)


def can_decide_bid(state: Dict[str, Any], player_id: str) -> bool:
    """判断玩家是否处于本轮唯一一次叫分决策机会。"""
    player = (state.get("players") or {}).get(player_id)
    return (
        state.get("phase") == PHASE_CALLING
        and state.get("currentPlayerId") == player_id
        and isinstance(player, dict)
        and not bool(player.get("callDecided"))
    )


def list_legal_bid_scores(state: Dict[str, Any], player_id: str) -> List[int]:
    """列出严格高于当前最高分的合法叫分，不包含不叫。"""
    if not can_decide_bid(state, player_id):
        return []
    highest_score = state.get("bidScore", 0)
    if type(highest_score) is not int or highest_score not in (0,) + BID_SCORES:
        raise ValidationException("当前最高叫分无效")
    return [score for score in BID_SCORES if score > highest_score]


def validate_bid_score(state: Dict[str, Any], player_id: str, score: Any) -> int:
    """在执行边界重新校验整数档位和本次决策资格。"""
    if type(score) is not int or score not in list_legal_bid_scores(state, player_id):
        raise ValidationException("叫分必须为高于当前最高分的 1、2、3 分")
    return score
