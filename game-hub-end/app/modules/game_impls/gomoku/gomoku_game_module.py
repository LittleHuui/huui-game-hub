"""五子棋策略回合游戏模块组装。"""

from app.modules.game_impls.gomoku.gomoku_action_catalog import GomokuActionCatalog
from app.modules.game_impls.gomoku.gomoku_candidate_scorer import GomokuCandidateScorer
from app.modules.game_impls.gomoku.gomoku_constants import GOMOKU_ACTION_TYPES
from app.modules.game_impls.gomoku.gomoku_enumerated_interaction import GomokuEnumeratedInteraction
from app.modules.game_impls.gomoku.gomoku_fallback_policy import GomokuFallbackPolicy
from app.modules.game_impls.gomoku.gomoku_lifecycle_engine import GomokuLifecycleEngine
from app.modules.game_impls.gomoku.gomoku_state_projector import GomokuStateProjector
from app.modules.strategy_turn.decision.candidate_selector import CandidateSelector
from app.modules.strategy_turn.game_module import StrategyTurnGameModule
from app.modules.strategy_turn.interaction.binding import ActionInteractionBinding


def build_gomoku_game_module() -> StrategyTurnGameModule:
    """
    组装五子棋游戏模块。

    :return: 五子棋策略回合游戏模块。
    """
    lifecycle = GomokuLifecycleEngine()
    projector = GomokuStateProjector()
    action_catalog = GomokuActionCatalog()
    bindings = []
    for action_type in GOMOKU_ACTION_TYPES:
        interaction = GomokuEnumeratedInteraction(action_catalog, action_type)
        bindings.append(
            ActionInteractionBinding(
                actionType=action_type,
                interactionMode="ENUMERATED",
                offerProvider=interaction,
                submissionResolver=interaction,
                automatedCandidateProvider=interaction,
                hintSuggestionProvider=interaction,
            )
        )
    return StrategyTurnGameModule(
        gameCode="gomoku",
        lifecycleEngine=lifecycle,
        stateProjector=projector,
        interactionBindings=bindings,
        candidateScorer=GomokuCandidateScorer(),
        candidateSelector=CandidateSelector(),
        fallbackPolicy=GomokuFallbackPolicy(),
    )
