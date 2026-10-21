import { onUnmounted, ref, watch } from 'vue';
import { useStrategyTurnGameView } from '../../../composables/useStrategyTurnGameView.js';
import { filterCardPlayedEvents } from '../unoGameViewUtils.js';

/**
 * 订阅平台 GameView 展示快照，供 UNO 页面渲染。
 */
export function useUnoGameView() {
  const {
    roomId,
    version,
    viewerPlayerId,
    currentPlayerId,
    publicState,
    privateState,
    actionOffers,
    frameEvents,
    playbackBusy,
    reset: resetStrategyView
  } = useStrategyTurnGameView();

  const cardPlayedEvents = ref([]);

  const stopRoomWatch = watch(roomId, (nextRoomId, prevRoomId) => {
    const next = String(nextRoomId || '').trim();
    const prev = String(prevRoomId || '').trim();
    if (next !== prev) {
      cardPlayedEvents.value = [];
    }
  });

  const stopVersionWatch = watch(
    version,
    (nextVersion, prevVersion) => {
      const next = Number(nextVersion) || 0;
      const prev = Number(prevVersion) || 0;
      if (next <= 0 && prev > 0) {
        cardPlayedEvents.value = [];
        return;
      }
      if (next <= prev) {
        return;
      }
      const played = filterCardPlayedEvents(frameEvents.value);
      if (played.length) {
        cardPlayedEvents.value = [...cardPlayedEvents.value, ...played];
      }
    },
    { flush: 'post' }
  );

  /**
   * 重置 UNO 事件展示和公共 GameView。
   * @returns {void}
   */
  function reset() {
    cardPlayedEvents.value = [];
    resetStrategyView();
  }

  /**
   * 停止 UNO 局部视图观察。
   * 房间生命周期负责释放共享 GameView 状态，UNO 视图不应影响其他订阅者。
   * @returns {void}
   */
  function dispose() {
    stopRoomWatch();
    stopVersionWatch();
  }

  onUnmounted(dispose);

  return {
    version,
    viewerPlayerId,
    currentPlayerId,
    publicState,
    privateState,
    actionOffers,
    playbackBusy,
    cardPlayedEvents,
    reset,
    dispose
  };
}
