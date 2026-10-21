"""托管自动决策服务。"""

import logging
import math
from typing import List, Optional, Set, Tuple

from app.common.exceptions import ValidationException
from app.core.clock import Clock, system_clock
from app.modules.strategy_turn.decision.candidate_selector import CandidateSelector
from app.modules.strategy_turn.decision.schemas import (
    CandidateContractError,
    ManagedDecisionResult,
    NoLegalCandidateError,
)
from app.modules.strategy_turn.game_module import StrategyTurnGameModule, StrategyTurnGameModuleRegistry
from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.interaction.gateway import ActionInteractionGateway
from app.modules.strategy_turn.schemas import (
    ActionCandidate,
    ActionDecisionContext,
    CandidateScore,
    ResolvedGameAction,
    RuntimeSnapshot,
)

logger = logging.getLogger(__name__)


class ManagedDecisionService(object):
    """统一托管决策服务。"""

    def __init__(
        self,
        module_registry: StrategyTurnGameModuleRegistry,
        interaction_gateway: ActionInteractionGateway,
        clock: Clock = system_clock,
    ) -> None:
        self._module_registry = module_registry
        self._interaction_gateway = interaction_gateway
        self._clock = clock
        self._default_selector = CandidateSelector()

    def decide(
        self,
        snapshot: RuntimeSnapshot,
        player_id: str,
        version: int,
        room_id: str,
    ) -> ManagedDecisionResult:
        """
        为托管或 AI 玩家选择动作提交。

        :param snapshot: 当前运行时快照。
        :param player_id: 决策玩家 ID。
        :param version: 房间版本。
        :param room_id: 房间 ID。
        :return: 决策结果。
        """
        game_code = str(snapshot.gameCode or "").strip()
        module = self._module_registry.require(game_code)
        interaction_context = ActionInteractionContext(
            gameCode=game_code,
            roomId=room_id,
            runtimeRule=snapshot.runtimeRule,
            state=snapshot.state,
            playerId=player_id,
            version=int(version),
            currentTimeMs=self._clock.now_ms(),
        )
        try:
            candidates = list(
                self._interaction_gateway.list_automated_candidates(interaction_context) or []
            )
        except ValidationException as exc:
            raise CandidateContractError("候选 Provider 返回无法解析的 submission") from exc
        if not candidates:
            raise NoLegalCandidateError("有效回合不存在合法自动候选")
        self._validate_candidate_contracts(interaction_context, candidates)
        if module.fallbackPolicy is None:
            raise CandidateContractError("游戏未注册 FallbackPolicy")
        decision_context = ActionDecisionContext(
            gameCode=game_code,
            roomId=room_id,
            playerId=player_id,
            runtimeRule=snapshot.runtimeRule,
            state=snapshot.state,
            version=int(version),
        )
        selected, scores, used_fallback, fallback_reason = self._choose_candidate(
            module,
            decision_context,
            candidates,
        )
        if selected is None:
            raise CandidateContractError("Fallback 未能选出合法候选")
        resolved = self._interaction_gateway.resolve_submission(
            interaction_context,
            selected.submission,
        )
        self._validate_resolved_candidate(selected, resolved)
        if used_fallback:
            logger.info(
                "managed decision used fallback, gameCode=%s roomId=%s playerId=%s reason=%s candidateId=%s",
                game_code,
                room_id,
                player_id,
                fallback_reason,
                selected.candidateId,
            )
        return ManagedDecisionResult(
            submission=selected.submission,
            candidate=selected,
            scores=scores,
            usedFallback=used_fallback,
            fallbackReason=fallback_reason,
        )

    def _choose_candidate(
        self,
        module: StrategyTurnGameModule,
        decision_context: ActionDecisionContext,
        candidates: List[ActionCandidate],
    ) -> Tuple[Optional[ActionCandidate], List[CandidateScore], bool, Optional[str]]:
        """
        对全部候选统一评分、选择，必要时走游戏兜底。

        :param module: 游戏模块。
        :param decision_context: 决策上下文。
        :param candidates: 已校验候选列表。
        :return: 选中候选、评分、是否兜底、兜底原因。
        """
        candidate_ids = self._candidate_id_set(candidates)
        selector = module.candidateSelector or self._default_selector
        scores = []  # type: List[CandidateScore]
        fallback_reason = None  # type: Optional[str]
        selected = None  # type: Optional[ActionCandidate]

        if module.candidateScorer is None:
            fallback_reason = "scorerMissing"
        else:
            try:
                scores = list(module.candidateScorer.score_candidates(decision_context, candidates) or [])
            except Exception:
                fallback_reason = "scorerException"
            else:
                fallback_reason = self._score_contract_issue(candidates, scores)

        if fallback_reason is None:
            try:
                selected = selector.select(candidates, scores)
            except Exception:
                fallback_reason = "selectorException"
            else:
                if selected is not None and selected.candidateId not in candidate_ids:
                    fallback_reason = "selectorOutOfSet"
                    selected = None
                elif selected is None:
                    fallback_reason = "selectorReturnedNone"

        if selected is not None:
            return selected, scores, False, None

        chosen = self._apply_fallback(module, decision_context, candidates, candidate_ids)
        return chosen, scores, True, fallback_reason

    def _apply_fallback(
        self,
        module: StrategyTurnGameModule,
        decision_context: ActionDecisionContext,
        candidates: List[ActionCandidate],
        candidate_ids: Set[str],
    ) -> Optional[ActionCandidate]:
        """
        调用游戏兜底策略，从已校验候选中保守选择。

        :param module: 游戏模块。
        :param decision_context: 决策上下文。
        :param candidates: 已校验候选列表。
        :param candidate_ids: 候选 ID 集合。
        :return: 兜底候选。
        """
        try:
            selected = module.fallbackPolicy.choose(decision_context, candidates)
        except Exception as exc:
            raise CandidateContractError("Fallback 执行失败") from exc
        if selected is None:
            return None
        if selected.candidateId not in candidate_ids:
            raise CandidateContractError("Fallback 返回候选集合外对象")
        return selected

    def _validate_candidate_contracts(
        self,
        interaction_context: ActionInteractionContext,
        candidates: List[ActionCandidate],
    ) -> None:
        """
        校验候选合同，包括 submission 可解析且与 normalizedAction 一致。

        :param interaction_context: 动作交互上下文。
        :param candidates: 候选列表。
        :return: 无。
        """
        seen_ids = set()  # type: Set[str]
        for candidate in candidates:
            candidate_id = str(candidate.candidateId or "").strip()
            if not candidate_id:
                raise CandidateContractError("candidateId 不能为空")
            if candidate_id in seen_ids:
                raise CandidateContractError("candidateId 不得重复")
            if candidate.actionType != candidate.submission.actionType:
                raise CandidateContractError("actionType 与 submission.actionType 不一致")
            seen_ids.add(candidate_id)
            try:
                resolved = self._interaction_gateway.resolve_submission(
                    interaction_context,
                    candidate.submission,
                )
            except ValidationException as exc:
                raise CandidateContractError("候选 submission 无法解析") from exc
            self._validate_resolved_candidate(candidate, resolved)

    def _validate_resolved_candidate(
        self,
        candidate: ActionCandidate,
        resolved: ResolvedGameAction,
    ) -> None:
        """
        校验候选 normalizedAction 与 Resolver 结果一致。

        :param candidate: 候选动作。
        :param resolved: Resolver 解析结果。
        :return: 无。
        """
        normalized = candidate.normalizedAction
        checks = {
            "actionType": (normalized.actionType, resolved.actionType),
            "actionId": (normalized.actionId, resolved.actionId),
            "playerId": (normalized.playerId, resolved.playerId),
        }
        for label, values in checks.items():
            if values[0] != values[1]:
                raise CandidateContractError(
                    "normalizedAction {0} 与 Resolve 结果不一致".format(label)
                )

    def _score_contract_issue(
        self,
        candidates: List[ActionCandidate],
        scores: List[CandidateScore],
    ) -> Optional[str]:
        """
        判断评分结果是否应触发兜底。

        :param candidates: 候选列表。
        :param scores: 评分列表。
        :return: 兜底原因；评分有效时返回 None。
        """
        if not scores:
            return "scorerEmpty"
        candidate_ids = self._candidate_id_set(candidates)
        seen_ids = set()  # type: Set[str]
        for score in scores:
            candidate_id = str(score.candidateId or "").strip()
            if candidate_id not in candidate_ids:
                return "scorerUnknownCandidateId"
            if candidate_id in seen_ids:
                return "scorerDuplicateCandidateId"
            if not math.isfinite(float(score.score)):
                return "scorerNonFiniteScore"
            seen_ids.add(candidate_id)
        if len(seen_ids) < len(candidate_ids):
            return "scorerPartialScores"
        return None

    def _candidate_id_set(self, candidates: List[ActionCandidate]) -> Set[str]:
        """
        提取候选 ID 集合。

        :param candidates: 候选列表。
        :return: 候选 ID 集合。
        """
        return {str(item.candidateId or "").strip() for item in candidates}
