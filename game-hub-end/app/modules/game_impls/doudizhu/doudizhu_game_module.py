"""斗地主策略回合游戏模块组装。"""



from app.modules.game_impls.doudizhu.doudizhu_candidate_scorer import DoudizhuCandidateScorer

from app.modules.game_impls.doudizhu.doudizhu_enumerated_interaction import DoudizhuEnumeratedInteraction

from app.modules.game_impls.doudizhu.doudizhu_fallback_policy import DoudizhuFallbackPolicy

from app.modules.game_impls.doudizhu.doudizhu_lifecycle_engine import DoudizhuLifecycleEngine

from app.modules.game_impls.doudizhu.doudizhu_play_cards_interaction import (

    DoudizhuPlayCardsInteraction,
    DoudizhuHintSuggestionProvider,

    DoudizhuPlayCardsRuleService,

)

from app.modules.game_impls.doudizhu.doudizhu_state_projector import DoudizhuStateProjector

from app.modules.strategy_turn.decision.candidate_selector import CandidateSelector

from app.modules.strategy_turn.game_module import StrategyTurnGameModule

from app.modules.strategy_turn.interaction.binding import ActionInteractionBinding



_ENUMERATED_ACTION_TYPES = (

    "SHOW_CARDS",

    "SKIP_SHOW_CARDS",

    "CALL_LANDLORD",

    "PASS_CALL",

    "ROB_LANDLORD",

    "PASS_ROB",

    "DOUBLE",

    "PASS_DOUBLE",

    "PASS",

)





def build_doudizhu_game_module() -> StrategyTurnGameModule:

    """

    组装斗地主游戏模块。



    :return: 斗地主策略回合游戏模块。

    """

    lifecycle_engine = DoudizhuLifecycleEngine()

    state_projector = DoudizhuStateProjector()

    bindings = []

    for action_type in _ENUMERATED_ACTION_TYPES:

        interaction = DoudizhuEnumeratedInteraction(action_type)

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

    play_rule_service = DoudizhuPlayCardsRuleService()

    play_interaction = DoudizhuPlayCardsInteraction(play_rule_service)

    bindings.append(

        ActionInteractionBinding(

            actionType="PLAY_CARDS",

            interactionMode="COMPOSED",

            offerProvider=play_interaction,

            submissionResolver=play_interaction,

            previewProvider=play_interaction,

            automatedCandidateProvider=play_interaction,

            hintSuggestionProvider=DoudizhuHintSuggestionProvider(play_interaction),

        )

    )

    return StrategyTurnGameModule(

        gameCode="doudizhu",

        lifecycleEngine=lifecycle_engine,

        stateProjector=state_projector,

        interactionBindings=bindings,

        candidateScorer=DoudizhuCandidateScorer(),

        candidateSelector=CandidateSelector(),

        fallbackPolicy=DoudizhuFallbackPolicy(),

    )
