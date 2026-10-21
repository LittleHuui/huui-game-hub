"""后台任务短重试与恢复退避策略。"""


class TaskRetryPolicy(object):
    """任务短重试与恢复周期配置。"""

    def __init__(
        self,
        retry_delays_ms,
        recovery_backoff_ms,
        max_recovery_count,
    ) -> None:
        """
        初始化任务重试策略。

        :param retry_delays_ms: 当前恢复周期内的短退避毫秒数组。
        :param recovery_backoff_ms: 恢复周期之间的长退避毫秒数组。
        :param max_recovery_count: 允许的最大恢复周期次数。
        """
        self.retry_delays_ms = list(retry_delays_ms)
        self.recovery_backoff_ms = list(recovery_backoff_ms)
        self.max_recovery_count = int(max_recovery_count)

    def recovery_delay_ms(self, recovery_count: int) -> int:
        """
        按恢复周期序号返回长退避毫秒。

        :param recovery_count: 即将开始的恢复周期序号（从 1 起）。
        :return: 长退避毫秒。
        """
        if not self.recovery_backoff_ms:
            return 0
        index = max(0, int(recovery_count) - 1)
        if index >= len(self.recovery_backoff_ms):
            index = len(self.recovery_backoff_ms) - 1
        return int(self.recovery_backoff_ms[index])


MANAGED_TASK_RETRY_POLICY = TaskRetryPolicy(
    retry_delays_ms=[100, 300, 700],
    recovery_backoff_ms=[2000, 5000, 15000],
    max_recovery_count=3,
)

AUTO_ADVANCE_TASK_RETRY_POLICY = TaskRetryPolicy(
    retry_delays_ms=[100, 300, 700],
    recovery_backoff_ms=[2000, 5000, 15000],
    max_recovery_count=3,
)
