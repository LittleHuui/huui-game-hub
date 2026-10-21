import { computed } from 'vue';
import {
  normalizeHandCard,
  resolveOpponentLayout,
  sortHandCards
} from '../doudizhuGameViewUtils.js';

/**
 * 构建斗地主牌桌、玩家方位和展示状态，不参与规则判定。
 * @param {object} input
 * @returns {object}
 */
export function useDoudizhuTableView(input) {
  const publicPlayers = computed(() =>
    Array.isArray(input.publicStateRef.value?.players)
      ? input.publicStateRef.value.players
      : []
  );
  const gameState = computed(() => input.publicStateRef.value?.gameState || {});
  const currentPlayerIdInTurn = computed(() =>
    String(input.currentPlayerIdRef.value || gameState.value?.currentPlayerId || '').trim()
  );
  const turnTimeoutSeconds = computed(() => {
    const started = Number(gameState.value?.currentTurnStartedAt) || 0;
    const deadline = Number(gameState.value?.currentTurnDeadlineAt) || 0;
    return !started || !deadline || deadline <= started
      ? 30
      : Math.max(1, Math.round((deadline - started) / 1000));
  });
  const turnDeadlineAtMs = computed(() => {
    const raw = Number(gameState.value?.currentTurnDeadlineAt);
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  });
  const handCards = computed(() => {
    const list = input.privateStateRef.value?.handCards;
    return Array.isArray(list)
      ? sortHandCards(list.map(normalizeHandCard).filter((card) => card.cardInstanceId))
      : [];
  });
  const passPlayerIds = computed(() =>
    Array.isArray(gameState.value?.passPlayerIds)
      ? gameState.value.passPlayerIds.map((id) => String(id || '').trim()).filter(Boolean)
      : []
  );
  const viewerRoomMember = computed(() =>
    input.currentRoomRef.value?.members?.find(
      (member) => String(member?.playerId || '').trim() === String(input.viewerIdRef.value || '').trim()
    ) || null
  );
  const viewerManagedActive = computed(
    () => String(viewerRoomMember.value?.managedMode || '').trim() === 'active'
  );
  const viewerPersonalMultiplier = computed(() => {
    const player = publicPlayers.value.find(
      (item) => String(item?.playerId || '').trim() === String(input.viewerIdRef.value || '').trim()
    );
    return Number(player?.personalMultiplier) || 1;
  });
  const viewerIsCurrentTurn = computed(
    () => input.viewerIdRef.value === currentPlayerIdInTurn.value
  );

  /**
   * 查找房间成员。
   * @param {string} playerId
   * @returns {object|null}
   */
  function findRoomMember(playerId) {
    return input.currentRoomRef.value?.members?.find(
      (member) => String(member?.playerId || '').trim() === playerId
    ) || null;
  }

  /**
   * 解析玩家昵称。
   * @param {string} playerId
   * @returns {string}
   */
  function resolvePlayerNickname(playerId) {
    return String(findRoomMember(playerId)?.nickname || '').trim() || playerId;
  }

  /**
   * 构建单个对手面板。
   * @param {object} playerState
   * @returns {object}
   */
  function buildOpponentPanel(playerState) {
    const playerId = String(playerState?.playerId || '').trim();
    const member = findRoomMember(playerId);
    const managedMode = String(member?.managedMode || '').trim();
    return {
      playerId,
      nickname: resolvePlayerNickname(playerId),
      playerState: playerState || {},
      isAi: Boolean(member?.isAi),
      managedLabel: managedMode === 'active' ? '托管中' : managedMode === 'shell' ? '离线托管' : '',
      managedBadgeClass: managedMode === 'active'
        ? 'managed-active'
        : managedMode === 'shell'
          ? 'managed-shell'
          : '',
      isCurrentTurn: playerId === currentPlayerIdInTurn.value
    };
  }

  const opponentLayout = computed(() =>
    resolveOpponentLayout(publicPlayers.value, input.viewerIdRef.value)
  );
  const leftOpponent = computed(() =>
    opponentLayout.value.left ? buildOpponentPanel(opponentLayout.value.left) : null
  );
  const rightOpponent = computed(() =>
    opponentLayout.value.right ? buildOpponentPanel(opponentLayout.value.right) : null
  );
  const lastPlayPlayerNickname = computed(() => {
    const playerId = String(gameState.value?.lastPlayPlayerId || '').trim();
    return playerId ? resolvePlayerNickname(playerId) : '';
  });
  const lastPassPlayerNickname = computed(() => {
    const passes = passPlayerIds.value;
    const playerId = Array.isArray(passes) ? String(passes[passes.length - 1] || '').trim() : '';
    return playerId ? resolvePlayerNickname(playerId) : '';
  });
  const lastActionEvent = computed(() => {
    const rawEvent = gameState.value?.lastActionEvent;
    if (!rawEvent || typeof rawEvent !== 'object') {
      return null;
    }
    const playerId = String(rawEvent.playerId || '').trim();
    const actionType = String(rawEvent.actionType || '').trim();
    return playerId && actionType ? { playerId, actionType } : null;
  });
  const lastActionPlayerNickname = computed(() => {
    const playerId = lastActionEvent.value?.playerId;
    return playerId ? resolvePlayerNickname(playerId) : '';
  });
  /**
   * Stateless table model reset hook.
   * @returns {void}
   */
  function reset() {}

  /**
   * Stateless table model dispose hook.
   * @returns {void}
   */
  function dispose() {}

  return {
    gameState,
    currentPlayerIdInTurn,
    turnTimeoutSeconds,
    turnDeadlineAtMs,
    handCards,
    passPlayerIds,
    viewerManagedActive,
    viewerPersonalMultiplier,
    viewerIsCurrentTurn,
    leftOpponent,
    rightOpponent,
    lastPlayPlayerNickname,
    lastPassPlayerNickname,
    lastActionEvent,
    lastActionPlayerNickname,
    reset,
    dispose
  };
}
