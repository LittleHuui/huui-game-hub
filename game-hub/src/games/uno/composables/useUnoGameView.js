import { ref, watch } from 'vue';
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
    legalActions,
    frameEvents,
    animationHint,
    playbackBusy
  } = useStrategyTurnGameView();

  const cardPlayedEvents = ref([]);

  watch(roomId, (nextRoomId, prevRoomId) => {
    const next = String(nextRoomId || '').trim();
    const prev = String(prevRoomId || '').trim();
    if (next !== prev) {
      cardPlayedEvents.value = [];
    }
  });

  watch(
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

  return {
    version,
    viewerPlayerId,
    currentPlayerId,
    publicState,
    privateState,
    legalActions,
    animationHint,
    playbackBusy,
    cardPlayedEvents
  };
}
