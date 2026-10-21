"""斗地主 PLAY_CARDS 构造型交互实现。"""

import base64
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from app.common.exceptions import ValidationException
from app.modules.game_impls.doudizhu.doudizhu_combo_rule import recognize_combo
from app.modules.game_impls.doudizhu.doudizhu_hint_play_search import find_legal_hint_play
from app.modules.game_impls.doudizhu.doudizhu_play_candidate_generator import (
    enumerate_play_candidates_structured,
)
from app.modules.game_impls.doudizhu.doudizhu_state_helpers import (
    build_combo_config,
    build_combo_signature,
    build_last_play_signature,
    parse_cards,
    parse_combo_info,
)
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo
from app.modules.strategy_turn.interaction.automated_candidate_provider import AutomatedCandidateProvider
from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.interaction.hint_suggestion_provider import HintSuggestionProvider
from app.modules.strategy_turn.interaction.offer_provider import ActionOfferProvider
from app.modules.strategy_turn.interaction.preview_provider import ActionPreviewProvider
from app.modules.strategy_turn.interaction.submission_resolver import ActionSubmissionResolver
from app.modules.strategy_turn.schemas import (
    ActionCandidate,
    ActionPreview,
    ActionSubmission,
    ComposedActionCapability,
    ComposedActionInput,
    ComposedActionOffer,
    ResolvedGameAction,
    HintSuggestion,
    HintSuggestionPage,
)

_ACTION_PLAY_CARDS = "PLAY_CARDS"
_PHASE_PLAYING = "playing"
_AUTOMATED_CANDIDATE_BUDGET = 1000
_HINT_CANDIDATE_BUDGET = 10000


class DoudizhuPlayCardsResolveResult(object):
    """斗地主出牌解析结果。"""

    def __init__(
        self,
        action_id: str,
        payload: Dict[str, Any],
        combo: DoudizhuComboInfo,
        cards: List[DoudizhuCard],
    ) -> None:
        self.action_id = action_id
        self.payload = payload
        self.combo = combo
        self.cards = cards


class DoudizhuPlayCardsRuleService(object):
    """斗地主 PLAY_CARDS 共享纯规则解析服务。"""

    def resolve_selection(
        self,
        context: ActionInteractionContext,
        card_instance_ids: List[str],
    ) -> DoudizhuPlayCardsResolveResult:
        """
        校验并解析出牌选择。

        :param context: 动作交互上下文。
        :param card_instance_ids: 客户端选择的牌实例 ID。
        :return: 出牌解析结果。
        """
        self._validate_turn(context)
        normalized_ids = self._normalize_card_ids(card_instance_ids)
        hand_cards = self._hand_cards(context.state, context.playerId)
        selected_cards = self._pick_cards(hand_cards, normalized_ids)
        combo_config = build_combo_config(context.state)
        last_play = parse_combo_info(context.state.get("lastPlay"))
        combo = recognize_combo(selected_cards, combo_config, last_play)
        if combo is None:
            if last_play is not None and recognize_combo(selected_cards, combo_config) is not None:
                raise ValidationException("出牌不能压过上家")
            raise ValidationException("出牌牌型不合法")
        sorted_ids = sorted(normalized_ids)
        combo_dict = combo.model_dump()
        payload = {
            "cardInstanceIds": sorted_ids,
            "normalizedCombo": combo_dict,
            "comboSignature": build_combo_signature(combo),
            "lastPlaySignature": build_last_play_signature(context.state),
        }
        payload.update(combo_dict)
        action_id = self._build_action_id(context, sorted_ids, combo)
        return DoudizhuPlayCardsResolveResult(action_id, payload, combo, selected_cards)

    def build_preview(
        self,
        context: ActionInteractionContext,
        card_instance_ids: List[str],
    ) -> ActionPreview:
        """
        构建只读出牌预览。

        :param context: 动作交互上下文。
        :param card_instance_ids: 客户端选择的牌实例 ID。
        :return: 预览结果。
        """
        if not card_instance_ids:
            return ActionPreview(
                status="INCOMPLETE",
                actionType=_ACTION_PLAY_CARDS,
                summary={},
                reason="请选择至少一张牌",
            )
        try:
            result = self.resolve_selection(context, card_instance_ids)
        except ValidationException as exc:
            return ActionPreview(
                status="INVALID",
                actionType=_ACTION_PLAY_CARDS,
                summary={},
                reason=str(exc),
            )
        return ActionPreview(
            status="VALID",
            actionType=_ACTION_PLAY_CARDS,
            summary={
                "actionId": result.action_id,
                "combo": result.combo.model_dump(),
                "cardInstanceIds": result.payload.get("cardInstanceIds") or [],
            },
            reason=None,
        )

    def list_candidate_results(
        self,
        context: ActionInteractionContext,
        limit: int,
    ) -> List[DoudizhuPlayCardsResolveResult]:
        """
        生成可通过完整校验的有限出牌候选。

        :param context: 动作交互上下文。
        :param limit: 最大数量。
        :return: 出牌解析结果列表。
        """
        self._validate_turn(context)
        hand_cards = self._hand_cards(context.state, context.playerId)
        combo_config = build_combo_config(context.state)
        last_play = parse_combo_info(context.state.get("lastPlay"))
        generated = enumerate_play_candidates_structured(hand_cards, combo_config, last_play)
        results = []
        seen = set()
        for combo, cards in generated:
            ids = sorted([card.cardInstanceId for card in cards])
            key = tuple(ids)
            if key in seen:
                continue
            seen.add(key)
            try:
                results.append(self.resolve_selection(context, ids))
            except ValidationException:
                continue
            if len(results) >= int(limit):
                break
        return results

    def verify_hint_result(
        self,
        context: ActionInteractionContext,
    ) -> Tuple[Optional[DoudizhuPlayCardsResolveResult], bool]:
        """
        在快速提示为空时核验合法牌，搜索未完成不能推断为无法出牌。

        :param context: 当前版本的动作交互上下文。
        :return: 补充提示结果与核验是否完成。
        """
        self._validate_turn(context)
        cards, complete = find_legal_hint_play(
            self._hand_cards(context.state, context.playerId),
            build_combo_config(context.state),
            parse_combo_info(context.state.get("lastPlay")),
        )
        if cards is None:
            return None, complete
        return self.resolve_selection(context, [card.cardInstanceId for card in cards]), True

    def _validate_turn(self, context: ActionInteractionContext) -> None:
        """
        校验当前是否允许该玩家出牌。

        :param context: 动作交互上下文。
        :return: 无。
        """
        if str(context.state.get("phase") or "") != _PHASE_PLAYING:
            raise ValidationException("当前阶段不能出牌")
        if str(context.state.get("currentPlayerId") or "").strip() != context.playerId:
            raise ValidationException("当前不是该玩家行动")

    def _normalize_card_ids(self, card_instance_ids: List[str]) -> List[str]:
        """
        规范化并校验选牌 ID。

        :param card_instance_ids: 原始牌实例 ID。
        :return: 规范化后的 ID 列表。
        """
        normalized = [str(item or "").strip() for item in card_instance_ids or []]
        normalized = [item for item in normalized if item]
        if not normalized:
            raise ValidationException("请选择至少一张牌")
        if len(normalized) != len(set(normalized)):
            raise ValidationException("不能重复选择同一张牌")
        return normalized

    def _hand_cards(self, state: Dict[str, Any], player_id: str) -> List[DoudizhuCard]:
        """
        读取玩家当前手牌。

        :param state: 对局状态。
        :param player_id: 玩家 ID。
        :return: 手牌列表。
        """
        players = state.get("players") or {}
        player = players.get(player_id) or {}
        return parse_cards(player.get("handCards") or [])

    def _pick_cards(
        self,
        hand_cards: List[DoudizhuCard],
        card_instance_ids: List[str],
    ) -> List[DoudizhuCard]:
        """
        按 ID 从手牌中取牌并校验归属。

        :param hand_cards: 当前手牌。
        :param card_instance_ids: 选牌 ID。
        :return: 选中的牌。
        """
        by_id = {card.cardInstanceId: card for card in hand_cards}
        selected = []
        for card_id in card_instance_ids:
            card = by_id.get(card_id)
            if card is None:
                raise ValidationException("选择的牌不在当前玩家手牌中")
            selected.append(card)
        return selected

    def _build_action_id(
        self,
        context: ActionInteractionContext,
        card_instance_ids: List[str],
        combo: DoudizhuComboInfo,
    ) -> str:
        """
        生成确定性的出牌动作 ID。

        :param context: 动作交互上下文。
        :param card_instance_ids: 排序后的牌实例 ID。
        :param combo: 归一化牌型。
        :return: 动作 ID。
        """
        combo_summary = "{0}:{1}:{2}".format(
            combo.comboType,
            combo.mainRankValue,
            combo.cardCount,
        )
        return "play|v{0}|{1}|{2}|{3}".format(
            int(context.version),
            context.playerId,
            ",".join(card_instance_ids),
            combo_summary,
        )


class DoudizhuPlayCardsInteraction(
    ActionOfferProvider,
    ActionSubmissionResolver,
    ActionPreviewProvider,
    AutomatedCandidateProvider,
):
    """斗地主 PLAY_CARDS 构造型交互。"""

    def __init__(self, rule_service: DoudizhuPlayCardsRuleService) -> None:
        self._rule_service = rule_service

    def build_offer(self, context: ActionInteractionContext) -> Optional[ComposedActionOffer]:
        """
        构建 PLAY_CARDS 构造能力 Offer。

        :param context: 动作交互上下文。
        :return: 构造型 Offer；不可出牌时返回 ``None``。
        """
        if not self._is_available(context):
            return None
        hand_count = len(self._rule_service._hand_cards(context.state, context.playerId))
        if hand_count <= 0:
            return None
        return ComposedActionOffer(
            actionType=_ACTION_PLAY_CARDS,
            interactionMode="COMPOSED",
            capability=ComposedActionCapability(
                selectionSource="HAND_CARDS",
                selectionMode="MULTIPLE",
                minPick=1,
                maxPick=hand_count,
                supportsPreview=True,
                supportsSuggestions=True,
            ),
        )

    def resolve(
        self,
        context: ActionInteractionContext,
        submission: ActionSubmission,
    ) -> ResolvedGameAction:
        """
        解析 PLAY_CARDS 提交。

        :param context: 动作交互上下文。
        :param submission: 外部动作意图。
        :return: 已解析动作。
        """
        card_ids = self._card_ids_from_submission(submission)
        result = self._rule_service.resolve_selection(context, card_ids)
        return ResolvedGameAction(
            actionId=result.action_id,
            actionType=_ACTION_PLAY_CARDS,
            playerId=context.playerId,
            payload=result.payload,
        )

    def preview(
        self,
        context: ActionInteractionContext,
        submission: ActionSubmission,
    ) -> ActionPreview:
        """
        预览 PLAY_CARDS 提交。

        :param context: 动作交互上下文。
        :param submission: 外部动作意图。
        :return: 预览结果。
        """
        return self._rule_service.build_preview(
            context,
            self._card_ids_from_submission(submission, allow_empty=True),
        )

    def list_candidates(
        self,
        context: ActionInteractionContext,
    ) -> List[ActionCandidate]:
        """
        返回 PLAY_CARDS 自动决策候选（预算由游戏内部控制）。

        :param context: 动作交互上下文。
        :return: 候选列表。
        """
        if not self._is_available(context):
            return []
        results = self._rule_service.list_candidate_results(
            context,
            _AUTOMATED_CANDIDATE_BUDGET,
        )
        return self._build_candidates(context, results)

    def list_page(
        self,
        context: ActionInteractionContext,
        cursor: Optional[str],
        page_size: int,
    ) -> HintSuggestionPage:
        """
        分页返回 PLAY_CARDS 用户提示候选。

        :param context: 动作交互上下文。
        :param cursor: 分页游标。
        :param page_size: 页大小。
        :return: 候选分页。
        """
        if not self._is_available(context):
            return HintSuggestionPage(items=[], nextCursor=None)
        results = self._rule_service.list_candidate_results(context, _HINT_CANDIDATE_BUDGET)
        if not results:
            verified_result, complete = self._rule_service.verify_hint_result(context)
            if verified_result is None:
                return HintSuggestionPage(
                    items=[],
                    nextCursor=None,
                    hasLegalAction=False if complete else None,
                )
            results = [verified_result]
        signature = self._build_cursor_signature(context)
        offset = self._decode_cursor(cursor, signature)
        limit = max(1, int(page_size or 20))
        selected = []
        for index in range(limit):
            if index >= len(results):
                break
            selected.append(results[(offset + index) % len(results)])
        next_offset = (offset + len(selected)) % len(results)
        return HintSuggestionPage(
            items=[
                HintSuggestion(
                    selection={
                        "cardInstanceIds": list(
                            result.payload.get("cardInstanceIds") or []
                        ),
                    },
                    summary={
                        "combo": dict(result.payload.get("normalizedCombo") or {}),
                    },
                )
                for result in selected
            ],
            nextCursor=self._encode_cursor(signature, next_offset),
            hasLegalAction=True,
        )

    def _list_hint_suggestions(
        self,
        context: ActionInteractionContext,
        cursor: Optional[str],
        page_size: int,
    ) -> HintSuggestionPage:
        """
        使用稳定游标查询用户连续提示候选。

        :param context: 动作交互上下文。
        :param cursor: 分页游标。
        :param page_size: 页大小。
        :return: 候选分页。
        """
        return self.list_page(context, cursor, page_size)

    def _build_candidates(
        self,
        context: ActionInteractionContext,
        results: List[DoudizhuPlayCardsResolveResult],
    ) -> List[ActionCandidate]:
        """
        将出牌解析结果转换为统一候选。

        :param context: 动作交互上下文。
        :param results: 出牌解析结果列表。
        :return: 统一候选列表。
        """
        candidates = []
        for result in results:
            card_ids = list(result.payload.get("cardInstanceIds") or [])
            submission = ActionSubmission(
                actionType=_ACTION_PLAY_CARDS,
                input=ComposedActionInput(
                    kind="COMPOSED",
                    selection={"cardInstanceIds": card_ids},
                ),
            )
            normalized = ResolvedGameAction(
                actionId=result.action_id,
                actionType=_ACTION_PLAY_CARDS,
                playerId=context.playerId,
                payload=result.payload,
            )
            candidates.append(
                ActionCandidate(
                    candidateId=result.action_id,
                    actionType=_ACTION_PLAY_CARDS,
                    submission=submission,
                    normalizedAction=normalized,
                    features={
                        "combo": result.combo.model_dump(),
                        "cardInstanceIds": card_ids,
                    },
                )
            )
        return candidates

    def _is_available(self, context: ActionInteractionContext) -> bool:
        """
        判断 PLAY_CARDS Provider 当前是否可用。

        :param context: 动作交互上下文。
        :return: 是否可提供出牌能力。
        """
        if str(context.state.get("phase") or "") != _PHASE_PLAYING:
            return False
        if str(context.state.get("currentPlayerId") or "").strip() != context.playerId:
            return False
        return True

    def _build_cursor_signature(self, context: ActionInteractionContext) -> str:
        """
        构建提示游标绑定的状态签名。

        :param context: 动作交互上下文。
        :return: 状态签名。
        """
        hand_cards = self._rule_service._hand_cards(context.state, context.playerId)
        last_play = context.state.get("lastPlay")
        payload = {
            "version": int(context.version),
            "playerId": context.playerId,
            "handCardIds": sorted([card.cardInstanceId for card in hand_cards]),
            "lastPlay": self._summarize_last_play(last_play),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _summarize_last_play(self, last_play: Any) -> Dict[str, Any]:
        """
        提取上一手出牌的游标摘要。

        :param last_play: 原始上一手出牌。
        :return: 摘要字典。
        """
        if not isinstance(last_play, dict):
            return {}
        keys = ["comboType", "mainRankValue", "cardCount", "chainLength", "cardInstanceIds"]
        return {key: last_play.get(key) for key in keys}

    def _encode_cursor(self, signature: str, offset: int) -> str:
        """
        编码下一页提示游标。

        :param signature: 状态签名。
        :param offset: 下一候选偏移。
        :return: URL 安全游标。
        """
        payload = {"signature": signature, "offset": int(offset)}
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")

    def _decode_cursor(self, cursor: Optional[str], signature: str) -> int:
        """
        解码并校验提示游标。

        :param cursor: 客户端传入游标。
        :param signature: 当前状态签名。
        :return: 可用偏移；失效时从头开始。
        """
        if not cursor:
            return 0
        try:
            raw = base64.urlsafe_b64decode(str(cursor).encode("ascii"))
            data = json.loads(raw.decode("utf-8"))
        except (TypeError, ValueError, UnicodeDecodeError):
            return 0
        if not isinstance(data, dict) or data.get("signature") != signature:
            return 0
        try:
            return max(0, int(data.get("offset") or 0))
        except (TypeError, ValueError):
            return 0

    def _card_ids_from_submission(
        self,
        submission: ActionSubmission,
        allow_empty: bool = False,
    ) -> List[str]:
        """
        从提交中读取牌实例 ID。

        :param submission: 外部动作意图。
        :param allow_empty: 是否允许空选择。
        :return: 牌实例 ID 列表。
        """
        if not isinstance(submission.input, ComposedActionInput):
            raise ValidationException("动作提交类型不匹配")
        selection = submission.input.selection or {}
        raw_ids = selection.get("cardInstanceIds")
        if raw_ids is None and allow_empty:
            return []
        if not isinstance(raw_ids, list):
            raise ValidationException("cardInstanceIds 必须为数组")
        return [str(item or "").strip() for item in raw_ids]


class DoudizhuHintSuggestionProvider(HintSuggestionProvider):
    """斗地主真人出牌提示适配器。"""

    def __init__(self, interaction: DoudizhuPlayCardsInteraction) -> None:
        """
        初始化真人提示适配器。
        :param interaction: 共享私有候选源的出牌交互实现。
        """
        self._interaction = interaction

    def list_page(
        self,
        context: ActionInteractionContext,
        cursor: Optional[str],
        page_size: int,
    ) -> HintSuggestionPage:
        """
        返回不暴露内部候选的出牌提示分页。
        :param context: 动作交互上下文。
        :param cursor: 分页游标。
        :param page_size: 页面大小。
        :return: 公开提示分页。
        """
        return self._interaction.list_page(context, cursor, page_size)
