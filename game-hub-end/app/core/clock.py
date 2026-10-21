"""统一时间与异步等待端口。"""

import asyncio
from typing import Optional

from app.core.time_utils import now_ms


class Clock(object):
    """提供可注入的毫秒时钟。"""

    def now_ms(self) -> int:
        """返回当前 Unix 毫秒时间。"""
        return int(now_ms())


class Sleeper(object):
    """提供可注入的异步等待。"""

    async def sleep_ms(self, delay_ms: int) -> None:
        """
        异步等待指定毫秒。
        :param delay_ms: 等待毫秒数。
        """
        await asyncio.sleep(max(0, int(delay_ms)) / 1000.0)


class CancellableSleeper(Sleeper):
    """可被外部唤醒的异步等待器，用于后台 Worker 优雅停止。"""

    def __init__(self) -> None:
        """初始化可取消等待器。"""
        self._wake = None  # type: Optional[asyncio.Event]
        self._loop = None  # type: Optional[asyncio.AbstractEventLoop]

    def cancel(self) -> None:
        """
        立即唤醒当前等待。

        :return: 无。
        """
        if self._wake is None:
            return
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._wake.set)
            return
        self._wake.set()

    async def sleep_ms(self, delay_ms: int) -> None:
        """
        异步等待指定毫秒，或在 ``cancel`` 时提前结束。

        :param delay_ms: 等待毫秒数。
        :return: 无。
        """
        current_loop = asyncio.get_running_loop()
        if self._wake is None or self._loop is not current_loop:
            self._wake = asyncio.Event()
            self._loop = current_loop
        self._wake.clear()
        try:
            await asyncio.wait_for(
                self._wake.wait(),
                timeout=max(0, int(delay_ms)) / 1000.0,
            )
        except asyncio.TimeoutError:
            pass


system_clock = Clock()
system_sleeper = Sleeper()
