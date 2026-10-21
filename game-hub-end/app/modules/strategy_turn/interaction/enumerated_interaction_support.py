"""枚举型动作交互共享辅助。"""

from app.modules.strategy_turn.schemas import (
    ActionCandidate,
    ActionSubmission,
    EnumeratedActionInput,
    ResolvedGameAction,
)


def option_to_resolved(option) -> ResolvedGameAction:
    """
    将枚举可选项转为已解析动作。

    :param option: 枚举可选项对象。
    :return: 已解析动作。
    """
    return ResolvedGameAction(
        actionId=option.actionId,
        actionType=option.actionType,
        playerId=option.playerId,
        payload=dict(option.payload or {}),
    )


def option_to_candidate(option) -> ActionCandidate:
    """
    将枚举可选项转为自动决策候选。

    :param option: 枚举可选项对象。
    :return: 动作候选。
    """
    submission = ActionSubmission(
        actionType=option.actionType,
        input=EnumeratedActionInput(kind="ENUMERATED", actionId=option.actionId),
    )
    normalized = option_to_resolved(option)
    return ActionCandidate(
        candidateId=option.actionId,
        actionType=option.actionType,
        submission=submission,
        normalizedAction=normalized,
        features={
            "payload": dict(option.payload or {}),
            "selection": dict(option.selection or {}),
        },
    )
