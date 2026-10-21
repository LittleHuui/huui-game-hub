import { computed } from 'vue';
import { useStrategyTurnTerminalFlow } from '../../../composables/useStrategyTurnTerminalFlow.js';

/**
 * 协调 UNO 终局弹窗、动画完成和延迟返回房间。
 * @param {object} input
 * @returns {object}
 */
export function useUnoTerminalFlow(input) {
  const terminalPlaybackBusy = computed(
    () => !input.isGameOverRef.value && Boolean(input.playbackBusyRef.value)
  );
  const flow = useStrategyTurnTerminalFlow({
    isGameOverRef: input.isGameOverRef,
    versionRef: input.versionRef,
    playbackBusyRef: terminalPlaybackBusy,
    roomIdRef: input.roomIdRef,
    resetGameView: input.resetGameView,
    navigate: input.navigate
  });
  return {
    settlementVisible: flow.visible,
    settlementDismissed: flow.dismissed,
    onSettlementClose: flow.close,
    reset: flow.reset,
    dispose: flow.dispose
  };
}
