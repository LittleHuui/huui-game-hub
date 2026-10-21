"""动作交互网关。"""



from typing import Dict, List, Set



from app.common.exceptions import ValidationException

from app.modules.strategy_turn.interaction.binding import ActionInteractionBinding

from app.modules.strategy_turn.interaction.context import ActionInteractionContext

from app.modules.strategy_turn.interaction.registry import ActionInteractionRegistry

from app.modules.strategy_turn.schemas import (

    ActionCandidate,


    ActionOffer,

    ActionPreview,

    ActionSubmission,

    HintSuggestionPage,

    ComposedActionOffer,

    EnumeratedActionOffer,

)





class ActionInteractionGateway(object):

    """统一分派动作 Offer、解析、预览和候选查询。"""



    __slots__ = ("__registry",)

    def __init__(self, registry: ActionInteractionRegistry) -> None:

        self.__registry = registry



    def build_offers(self, context: ActionInteractionContext) -> List[ActionOffer]:

        """

        构建当前玩家全部动作 Offer。



        :param context: 动作交互上下文。

        :return: 动作 Offer 列表。

        """

        offers = []

        for binding in self.__registry.list_bindings(context.gameCode):

            offer = binding.offerProvider.build_offer(context)

            if offer is None:

                continue

            self._validate_offer_contract(binding, offer)

            if isinstance(offer, EnumeratedActionOffer) and not offer.options:

                continue

            offers.append(offer)

        return offers



    def resolve_submission(

        self,

        context: ActionInteractionContext,

        submission: ActionSubmission,

    ):

        """

        解析外部动作提交。



        :param context: 动作交互上下文。

        :param submission: 外部动作意图。

        :return: 已解析动作。

        """

        binding = self.__registry.require(context.gameCode, submission.actionType)

        return binding.submissionResolver.resolve(context, submission)



    def preview(

        self,

        context: ActionInteractionContext,

        submission: ActionSubmission,

    ) -> ActionPreview:

        """

        预览动作提交。



        :param context: 动作交互上下文。

        :param submission: 外部动作意图。

        :return: 预览结果。

        """

        binding = self.__registry.require(context.gameCode, submission.actionType)

        if binding.previewProvider is None:

            raise ValidationException("动作不支持预览")

        return binding.previewProvider.preview(context, submission)



    def list_automated_candidates(

        self,

        context: ActionInteractionContext,

    ) -> List[ActionCandidate]:

        """

        汇总全部支持自动决策的动作候选。



        :param context: 动作交互上下文。

        :return: 候选动作列表。

        """

        candidates = []

        seen_ids = set()  # type: Set[str]

        for binding in self.__registry.list_bindings(context.gameCode):

            provider = binding.automatedCandidateProvider

            if provider is None:

                continue

            for candidate in provider.list_candidates(context) or []:

                self._validate_candidate_contract(binding, candidate, context, seen_ids)

                candidates.append(candidate)

        return candidates



    def list_hint_suggestions(

        self,

        context: ActionInteractionContext,

        action_type: str,

        cursor: str,

        page_size: int,

    ) -> HintSuggestionPage:

        """

        分页查询面向前端的动作提示。



        :param context: 动作交互上下文。

        :param action_type: 动作类型。

        :param cursor: 分页游标。

        :param page_size: 页大小。

        :return: 提示分页响应。

        """

        binding = self.__registry.require(context.gameCode, action_type)
        provider = binding.hintSuggestionProvider
        if provider is None:
            raise ValidationException("动作不支持用户提示")
        return provider.list_page(context, cursor or None, int(page_size))



    def _validate_offer_contract(self, binding: ActionInteractionBinding, offer: ActionOffer) -> None:

        """

        校验 Offer 与 Binding 声明一致。



        :param binding: 动作交互绑定。

        :param offer: Provider 返回的 Offer。

        :return: 无。

        """

        if offer.actionType != binding.actionType:

            raise ValidationException("动作 Offer actionType 与 Binding 不一致")

        if offer.interactionMode != binding.interactionMode:

            raise ValidationException("动作 Offer interactionMode 与 Binding 不一致")

        if isinstance(offer, ComposedActionOffer):

            capability = offer.capability

            if capability.supportsPreview != binding.supports_preview:

                raise ValidationException("COMPOSED Offer supportsPreview 与 Binding 不一致")

            if capability.supportsSuggestions != binding.supports_hint:

                raise ValidationException("COMPOSED Offer supportsSuggestions 与 Binding 不一致")



    def _validate_candidate_contract(

        self,

        binding: ActionInteractionBinding,

        candidate: ActionCandidate,

        context: ActionInteractionContext,

        seen_ids: Set[str],

    ) -> None:

        """

        校验候选动作与 Binding、当前玩家一致。



        :param binding: 动作交互绑定。

        :param candidate: 候选动作。

        :param context: 动作交互上下文。

        :param seen_ids: 本次结果已出现候选 ID。

        :return: 无。

        """

        candidate_id = str(candidate.candidateId or "").strip()

        if not candidate_id:

            raise ValidationException("candidateId 不能为空")

        if candidate_id in seen_ids:

            raise ValidationException("candidateId 不得重复")

        checks = {

            "candidate.actionType": candidate.actionType,

            "submission.actionType": candidate.submission.actionType,

            "normalizedAction.actionType": candidate.normalizedAction.actionType,

        }  # type: Dict[str, str]

        for label, action_type in checks.items():

            if action_type != binding.actionType:

                raise ValidationException("{0} 与 Binding 不一致".format(label))

        if candidate.normalizedAction.playerId != context.playerId:

            raise ValidationException("候选动作玩家与当前上下文不一致")

        seen_ids.add(candidate_id)
