"""UNO 策略回合游戏模块组装。"""

from app.modules.game_impls.uno.uno_constants import UNO_ACTION_TYPES
from app.modules.game_impls.uno.uno_candidate_scorer import UnoCandidateScorer
from app.modules.game_impls.uno.uno_enumerated_interaction import (
    UnoAutomatedCandidateProvider,
    UnoEnumeratedActionCatalog,
    UnoEnumeratedInteraction,
    UnoHintSuggestionProvider,
)
from app.modules.game_impls.uno.uno_fallback_policy import UnoFallbackPolicy
from app.modules.game_impls.uno.uno_lifecycle_engine import UnoLifecycleEngine
from app.modules.game_impls.uno.uno_state_projector import UnoStateProjector
from app.modules.strategy_turn.decision.candidate_selector import CandidateSelector
from app.modules.strategy_turn.game_module import StrategyTurnGameModule
from app.modules.strategy_turn.interaction.binding import ActionInteractionBinding


def build_uno_game_module() -> StrategyTurnGameModule:
    """
    组装 UNO 游戏模块。

    :return: UNO 策略回合游戏模块。
    """
    lifecycle = UnoLifecycleEngine()
    projector = UnoStateProjector()
    action_catalog = UnoEnumeratedActionCatalog()
    bindings = []
    for action_type in UNO_ACTION_TYPES:
        interaction = UnoEnumeratedInteraction(action_catalog, action_type)
        bindings.append(
            ActionInteractionBinding(
                actionType=action_type,
                interactionMode="ENUMERATED",
                offerProvider=interaction,
                submissionResolver=interaction,
                automatedCandidateProvider=UnoAutomatedCandidateProvider(action_catalog, action_type),
                hintSuggestionProvider=UnoHintSuggestionProvider(action_catalog, action_type),
            )
        )
    return StrategyTurnGameModule(
        gameCode="uno",
        lifecycleEngine=lifecycle,
        stateProjector=projector,
        interactionBindings=bindings,
        candidateScorer=UnoCandidateScorer(),
        candidateSelector=CandidateSelector(),
        fallbackPolicy=UnoFallbackPolicy(),
    )
