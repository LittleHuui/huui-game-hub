import { computed } from 'vue';
import { hasOfferByActionType } from '../../../services/action-interaction/actionOfferUtils.js';

/**
 * 构建五子棋棋盘、执棋颜色、玩家面板和悔棋展示状态。
 * @param {object} input
 * @returns {object}
 */
export function useGomokuPlayViewModel(input) {
  const gameState = computed(() => input.publicStateRef.value?.gameState || {});
  const boardMatrix = computed(() =>
    Array.isArray(gameState.value.board) ? gameState.value.board : []
  );
  const boardSize = computed(() => Number(gameState.value.boardSize) || 15);
  const lastPlaceRow = computed(() => gameState.value.lastPlaceRow);
  const lastPlaceCol = computed(() => gameState.value.lastPlaceCol);
  const turnDeadlineAtMs = computed(() => Number(gameState.value.currentTurnDeadlineAt) || null);
  const turnTimeoutSeconds = computed(() => {
    const started = Number(gameState.value.currentTurnStartedAt) || 0;
    const deadline = Number(gameState.value.currentTurnDeadlineAt) || 0;
    return !started || !deadline || deadline <= started
      ? 30
      : Math.max(1, Math.round((deadline - started) / 1000));
  });
  const viewerRoomMember = computed(() =>
    input.currentRoomRef.value?.members?.find(
      (member) =>
        String(member?.playerId || '').trim() === String(input.viewerIdRef.value || '').trim()
    ) || null
  );
  const viewerManagedActive = computed(
    () => String(viewerRoomMember.value?.managedMode || '').trim() === 'active'
  );

  /**
   * 查找房间成员并构建玩家面板。
   * @param {object} playerState
   * @param {string} playerId
   * @returns {object}
   */
  function buildPanel(playerState, playerId) {
    const member = input.currentRoomRef.value?.members?.find(
      (item) => String(item?.playerId || '').trim() === playerId
    );
    const nickname = String(member?.nickname || '').trim() || playerId;
    const managedMode = String(member?.managedMode || '').trim();
    const stone = String(playerState?.stone || '').toUpperCase();
    return {
      playerId,
      nickname,
      avatar: String(member?.avatar || '').trim(),
      avatarInitial: nickname ? nickname.charAt(0) : '?',
      stoneTone: stone === 'WHITE' ? 'white' : stone === 'BLACK' ? 'black' : '',
      isAi: Boolean(member?.isAi),
      isManaged: ['active', 'shell'].includes(managedMode),
      managedLabel: managedMode === 'active' ? '托管中' : managedMode === 'shell' ? '离线托管' : '',
      managedBadgeClass: managedMode === 'active'
        ? 'managed-active'
        : managedMode === 'shell'
          ? 'managed-shell'
          : '',
      isCurrentTurn: playerId === String(input.currentPlayerIdRef.value || '').trim()
    };
  }

  const players = computed(() =>
    Array.isArray(input.publicStateRef.value?.players)
      ? input.publicStateRef.value.players
      : []
  );
  const selfPanel = computed(() => {
    const viewerId = String(input.viewerIdRef.value || '').trim();
    const player = players.value.find(
      (item) => String(item?.playerId || '').trim() === viewerId
    );
    return player ? buildPanel(player, viewerId) : null;
  });
  const opponentPanel = computed(() => {
    const viewerId = String(input.viewerIdRef.value || '').trim();
    const player = players.value.find(
      (item) => String(item?.playerId || '').trim() !== viewerId
    );
    const playerId = String(player?.playerId || '').trim();
    return player ? buildPanel(player, playerId) : null;
  });
  const viewerStone = computed(() => {
    const viewerId = String(input.viewerIdRef.value || '').trim();
    const player = players.value.find(
      (item) => String(item?.playerId || '').trim() === viewerId
    );
    return String(player?.stone || 'BLACK');
  });
  const viewerIsCurrentTurn = computed(
    () =>
      String(input.currentPlayerIdRef.value || '').trim() ===
      String(input.viewerIdRef.value || '').trim()
  );
  const hasPlaceStoneOffer = computed(() =>
    hasOfferByActionType(input.actionOffersRef?.value, 'PLACE_STONE')
  );
  const boardInteractive = computed(
    () =>
      hasPlaceStoneOffer.value &&
      !viewerManagedActive.value &&
      !input.isGameOverRef.value
  );
  const boardDisabled = computed(
    () =>
      input.actionBusyRef.value ||
      !input.canShowRef.value ||
      input.isGameOverRef.value
  );
  const actionDisabled = computed(
    () => boardDisabled.value || viewerManagedActive.value
  );
  const hasPendingOwnUndoRequest = computed(
    () =>
      String(gameState.value.undoRequest?.requesterPlayerId || '').trim() ===
      String(input.viewerIdRef.value || '').trim()
  );
  const hasPendingIncomingUndoRequest = computed(
    () =>
      String(gameState.value.undoRequest?.targetPlayerId || '').trim() ===
      String(input.viewerIdRef.value || '').trim()
  );

  /**
   * Stateless view model reset hook.
   * @returns {void}
   */
  function reset() {}

  /**
   * Stateless view model dispose hook.
   * @returns {void}
   */
  function dispose() {}

  return {
    gameState,
    boardMatrix,
    boardSize,
    lastPlaceRow,
    lastPlaceCol,
    turnDeadlineAtMs,
    turnTimeoutSeconds,
    viewerManagedActive,
    selfPanel,
    opponentPanel,
    viewerStone,
    viewerIsCurrentTurn,
    hasPlaceStoneOffer,
    boardInteractive,
    boardDisabled,
    actionDisabled,
    hasPendingOwnUndoRequest,
    hasPendingIncomingUndoRequest,
    reset,
    dispose
  };
}
