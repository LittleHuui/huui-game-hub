import { computed, onUnmounted, ref, watch } from 'vue';
import { normalizeHandCard } from '../unoGameViewUtils.js';
import {
  applyUnoPlayerActionEvents,
  buildUnoPlayerActionMap,
  clearUnoPlayerActionForCurrentTurn,
  createEmptyUnoPlayerActionMap
} from '../unoPlayerActionViewModel.js';

/**
 * 构建 UNO 页面展示模型、镜像玩家分栏和事件展示状态。
 * @param {object} input
 * @returns {object}
 */
export function useUnoPlayViewModel(input) {
  const accumulatedPlayerActions = ref(createEmptyUnoPlayerActionMap());
  const currentPlayerIdInTurn = computed(() =>
    String(input.currentPlayerIdRef.value || input.publicStateRef.value?.currentPlayerId || '').trim()
  );
  const viewerRoomMember = computed(() =>
    input.currentRoomRef.value?.members?.find(
      (member) =>
        String(member?.playerId || '').trim() === String(input.viewerIdRef.value || '').trim()
    ) || null
  );
  const viewerManagedActive = computed(
    () => String(viewerRoomMember.value?.managedMode || '').trim() === 'active'
  );
  const currentColor = computed(() =>
    String(input.publicStateRef.value?.currentColor || '').trim()
  );
  const discardPileRecentCards = computed(() => {
    const list = input.publicStateRef.value?.discardPileRecentCards;
    return Array.isArray(list) ? list : [];
  });
  const turnTimeoutSeconds = computed(() => {
    const raw = Number(input.publicStateRef.value?.turnTimeoutSeconds);
    return Number.isFinite(raw) && raw > 0 ? raw : 60;
  });
  const turnDeadlineAtMs = computed(() => {
    const raw = Number(input.publicStateRef.value?.currentTurnDeadlineAt);
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  });
  const handCards = computed(() => {
    const list = input.privateStateRef.value?.handCards;
    return Array.isArray(list)
      ? list.map(normalizeHandCard).filter((card) => card.cardInstanceId)
      : [];
  });
  const handItems = computed(() =>
    handCards.value.map((card) => ({
      id: card.cardInstanceId,
      cardCode: card.cardCode,
      cardType: card.cardType
    }))
  );
  const viewerIsCurrentTurn = computed(
    () => input.viewerIdRef.value === currentPlayerIdInTurn.value
  );
  const interactionDisabled = computed(
    () =>
      !input.canShowRef.value ||
      input.isGameOverRef.value ||
      input.actionBusyRef.value ||
      viewerManagedActive.value ||
      !viewerIsCurrentTurn.value
  );
  const manualActionDisabled = computed(
    () =>
      !input.canShowRef.value ||
      input.isGameOverRef.value ||
      input.actionBusyRef.value ||
      !viewerIsCurrentTurn.value
  );
  const settlementRankings = computed(() => {
    const list = input.publicStateRef.value?.rankings;
    return Array.isArray(list) ? list : [];
  });
  const settlementPlayers = computed(() => {
    const list = input.publicStateRef.value?.players;
    return Array.isArray(list) ? list : [];
  });

  /**
   * 查找房间成员。
   * @param {string} playerId
   * @returns {object|null}
   */
  function findMember(playerId) {
    return input.currentRoomRef.value?.members?.find(
      (member) => String(member?.playerId || '').trim() === playerId
    ) || null;
  }

  /**
   * 构建对手展示面板。
   * @param {object} player
   * @returns {object}
   */
  function buildOpponent(player) {
    const playerId = String(player?.playerId || '').trim();
    const member = findMember(playerId);
    const managedMode = String(member?.managedMode || '').trim();
    const finishRank = Number(player?.finishRank);
    return {
      playerId,
      nickname: String(member?.nickname || '').trim() || playerId,
      handCount: Number(player?.handCount) || 0,
      isAi: Boolean(member?.isAi ?? player?.isAi),
      isManaged: ['active', 'shell'].includes(managedMode),
      managedLabel: managedMode === 'active' ? '托管中' : managedMode === 'shell' ? '离线托管' : '',
      managedBadgeClass: managedMode === 'active'
        ? 'managed-active'
        : managedMode === 'shell'
          ? 'managed-shell'
          : '',
      isCurrentTurn: playerId === currentPlayerIdInTurn.value,
      finishRank: Number.isFinite(finishRank) && finishRank > 0 ? finishRank : null
    };
  }

  const opponentPanels = computed(() => {
    const players = input.publicStateRef.value?.players;
    return Array.isArray(players)
      ? players
          .filter(
            (player) =>
              String(player?.playerId || '').trim() !== String(input.viewerIdRef.value || '').trim()
          )
          .map(buildOpponent)
      : [];
  });
  const leftPlayerPanels = computed(() => {
    const midpoint = Math.ceil(opponentPanels.value.length / 2);
    return opponentPanels.value.length <= 1
      ? opponentPanels.value
      : opponentPanels.value.slice(0, midpoint);
  });
  const rightPlayerPanels = computed(() => {
    if (opponentPanels.value.length <= 1) return [];
    return opponentPanels.value.slice(Math.ceil(opponentPanels.value.length / 2));
  });
  const playerActionMap = computed(() =>
    buildUnoPlayerActionMap(
      accumulatedPlayerActions.value,
      input.publicStateRef.value,
      input.isGameOverRef.value
    )
  );

  const stops = [
    watch(input.roomIdRef, (next, previous) => {
      if (next !== previous) accumulatedPlayerActions.value = createEmptyUnoPlayerActionMap();
    }),
    watch(input.versionRef, (nextVersion, previousVersion) => {
      const next = Number(nextVersion) || 0;
      const previous = Number(previousVersion) || 0;
      if (next <= 0 && previous > 0) {
        accumulatedPlayerActions.value = createEmptyUnoPlayerActionMap();
      } else if (next > previous && input.frameEventsRef.value?.length) {
        accumulatedPlayerActions.value = applyUnoPlayerActionEvents(
          accumulatedPlayerActions.value,
          input.frameEventsRef.value
        );
      }
    }),
    watch(currentPlayerIdInTurn, (nextPlayerId, previousPlayerId) => {
      if (!nextPlayerId || nextPlayerId === previousPlayerId || !input.publicStateRef.value) return;
      accumulatedPlayerActions.value = clearUnoPlayerActionForCurrentTurn(
        accumulatedPlayerActions.value,
        input.publicStateRef.value
      );
    })
  ];

  /**
   * 重置事件展示状态。
   * @returns {void}
   */
  function reset() {
    accumulatedPlayerActions.value = createEmptyUnoPlayerActionMap();
  }

  /**
   * 停止页面展示观察。
   * @returns {void}
   */
  function dispose() {
    stops.forEach((stop) => stop());
    reset();
  }

  onUnmounted(dispose);
  return {
    currentPlayerIdInTurn,
    viewerManagedActive,
    currentColor,
    discardPileRecentCards,
    turnTimeoutSeconds,
    turnDeadlineAtMs,
    handCards,
    handItems,
    viewerIsCurrentTurn,
    interactionDisabled,
    manualActionDisabled,
    settlementRankings,
    settlementPlayers,
    leftPlayerPanels,
    rightPlayerPanels,
    playerActionMap,
    reset,
    dispose
  };
}
