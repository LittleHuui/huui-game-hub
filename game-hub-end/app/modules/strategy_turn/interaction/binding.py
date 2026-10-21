"""动作交互绑定模型。"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.exceptions import ValidationException
from app.modules.strategy_turn.interaction.automated_candidate_provider import AutomatedCandidateProvider
from app.modules.strategy_turn.interaction.hint_suggestion_provider import HintSuggestionProvider
from app.modules.strategy_turn.interaction.offer_provider import ActionOfferProvider
from app.modules.strategy_turn.interaction.preview_provider import ActionPreviewProvider
from app.modules.strategy_turn.interaction.submission_resolver import ActionSubmissionResolver


class ActionInteractionBinding(BaseModel):
    """单个 actionType 的交互组件绑定。"""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    actionType: str = Field(min_length=1, description="动作类型")
    interactionMode: Literal["ENUMERATED", "COMPOSED"]
    offerProvider: ActionOfferProvider
    submissionResolver: ActionSubmissionResolver
    previewProvider: Optional[ActionPreviewProvider] = None
    automatedCandidateProvider: Optional[AutomatedCandidateProvider] = None
    hintSuggestionProvider: Optional[HintSuggestionProvider] = None

    @model_validator(mode="after")
    def validate_binding(self):
        """
        校验绑定组件完整性。

        :return: 当前绑定。
        :raises ValidationException: 绑定缺少必要 Provider 时抛出。
        """
        if self.interactionMode not in ("ENUMERATED", "COMPOSED"):
            raise ValidationException("interactionMode 必填且必须为 ENUMERATED 或 COMPOSED")
        return self

    @property
    def supports_preview(self) -> bool:
        """
        是否支持动作预览。

        :return: 存在 PreviewProvider 时为 True。
        """
        return self.previewProvider is not None

    @property
    def supports_automated_decision(self) -> bool:
        """
        是否支持自动决策。

        :return: 存在 AutomatedCandidateProvider 时为 True。
        """
        return self.automatedCandidateProvider is not None

    @property
    def supports_hint(self) -> bool:
        """
        是否支持用户提示。

        :return: 存在 HintSuggestionProvider 时为 True。
        """
        return self.hintSuggestionProvider is not None
