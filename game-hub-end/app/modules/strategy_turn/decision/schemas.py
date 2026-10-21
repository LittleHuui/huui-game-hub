"""策略回合自动决策模型。"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.strategy_turn.schemas import ActionCandidate, ActionSubmission, CandidateScore


class CandidateContractError(RuntimeError):
    """自动候选违反内部合同。"""


class CandidateSelectionError(RuntimeError):
    """候选选择结果无效。"""


class NoLegalCandidateError(RuntimeError):
    """有效回合不存在合法自动候选。"""


class ManagedDecisionResult(BaseModel):
    """自动决策结果。"""

    model_config = ConfigDict(extra="forbid")

    submission: Optional[ActionSubmission] = Field(default=None, description="选中的动作提交")
    candidate: Optional[ActionCandidate] = Field(default=None, description="选中的候选")
    scores: List[CandidateScore] = Field(default_factory=list, description="评分列表")
    usedFallback: bool = Field(default=False, description="是否通过兜底策略完成选择")
    fallbackReason: Optional[str] = Field(default=None, description="触发兜底的原因")
