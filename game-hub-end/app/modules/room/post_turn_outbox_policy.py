"""Post-turn Outbox task policies."""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class PostTurnOutboxPolicy(object):
    """Retry and recovery policy for one Outbox task type."""

    maxShortRetryCount: int
    maxRecoveryCount: int
    retryBackoffMs: Tuple[int, ...]
    recoveryBackoffMs: Tuple[int, ...]


DEFAULT_OUTBOX_POLICY = PostTurnOutboxPolicy(
    maxShortRetryCount=5,
    maxRecoveryCount=24,
    retryBackoffMs=(5000, 10000, 30000, 60000, 120000),
    recoveryBackoffMs=(30000, 60000, 120000, 300000),
)

POST_TURN_OUTBOX_POLICIES: Dict[str, PostTurnOutboxPolicy] = {
    "postTurnPlan": PostTurnOutboxPolicy(
        maxShortRetryCount=3,
        maxRecoveryCount=96,
        retryBackoffMs=(1000, 3000, 5000),
        recoveryBackoffMs=(5000, 15000, 30000, 60000),
    ),
    "GAME_SETTLEMENT": PostTurnOutboxPolicy(
        maxShortRetryCount=5,
        maxRecoveryCount=96,
        retryBackoffMs=(5000, 10000, 30000, 60000, 120000),
        recoveryBackoffMs=(30000, 60000, 120000, 300000),
    ),
    "TERMINAL_FINALIZE": PostTurnOutboxPolicy(
        maxShortRetryCount=3,
        maxRecoveryCount=288,
        retryBackoffMs=(1000, 3000, 5000),
        recoveryBackoffMs=(5000, 15000, 30000, 60000),
    ),
    "TERMINAL_DERIVED_CLEANUP": PostTurnOutboxPolicy(
        maxShortRetryCount=3,
        maxRecoveryCount=288,
        retryBackoffMs=(1000, 3000, 5000),
        recoveryBackoffMs=(5000, 15000, 30000, 60000),
    ),
}


def get_outbox_policy(task_type: str) -> PostTurnOutboxPolicy:
    """Return the policy for a task type."""
    return POST_TURN_OUTBOX_POLICIES.get(str(task_type or "").strip(), DEFAULT_OUTBOX_POLICY)


def pick_backoff(delays: Tuple[int, ...], count: int) -> int:
    """Pick a stable backoff from a retry/recovery delay table."""
    if not delays:
        return 5000
    index = max(0, min(int(count), len(delays) - 1))
    return int(delays[index])
