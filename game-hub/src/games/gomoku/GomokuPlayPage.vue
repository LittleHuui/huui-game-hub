<template>
  <div class="gomoku-page">
    <p v-if="loading" class="empty-text gomoku-page__status">正在加载房间与对局信息…</p>
    <p v-else-if="loadError" class="empty-text gomoku-page__status">{{ loadError }}</p>
    <p v-else-if="gameViewLoadError" class="empty-text gomoku-page__status">
      {{ gameViewLoadError }}
    </p>

    <div v-else-if="shellRejoinOffered" class="gomoku-page__status">
      <p class="empty-text">你已退出对局，席位由托管保留。重新加入后可继续对局。</p>
      <div class="gomoku-page__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--primary game-action-btn--sm"
          :disabled="rejoinBusy"
          @click="onRejoinRoom"
        >
          {{ rejoinBusy ? '处理中…' : '重新加入' }}
        </button>
        <button
          type="button"
          class="game-action-btn game-action-btn--ghost game-action-btn--sm"
          @click="onBackToLobby"
        >
          返回大厅
        </button>
      </div>
    </div>

    <div v-else-if="!canShowGameView" class="gomoku-page__status">
      <p class="empty-text">正在校验房间状态…</p>
    </div>

    <div v-else class="gomoku-page__playing">
      <header class="gomoku-page__play-bar">
        <span class="muted-small">{{ playRoomLabel }}</span>
        <button
          type="button"
          class="game-action-btn game-action-btn--warning game-action-btn--sm"
          @click="onExitRoomWithShell"
        >
          离开房间
        </button>
      </header>

      <div class="gomoku-battle-layout">
        <div v-if="opponentPanel" class="gomoku-opponent-panel">
          <article
            class="gomoku-player-card"
            :class="{ 'gomoku-player-card--active': opponentPanel.isCurrentTurn }"
          >
            <div class="gomoku-player-card__avatar">
              <img
                v-if="opponentPanel.avatar"
                :src="opponentPanel.avatar"
                :alt="opponentPanel.nickname"
              />
              <span v-else aria-hidden="true">{{ opponentPanel.avatarInitial }}</span>
            </div>
            <div class="gomoku-player-card__main">
              <h3 class="gomoku-player-card__name" :title="opponentPanel.nickname">
                {{ opponentPanel.nickname }}
              </h3>
              <div v-if="opponentPanel.stoneTone" class="gomoku-player-card__stone">
                <span
                  class="gomoku-stone-indicator"
                  :class="opponentPanel.stoneTone"
                />
              </div>
              <div
                v-if="opponentPanel.isAi || opponentPanel.managedLabel"
                class="gomoku-player-card__tags"
              >
                <span
                  v-if="opponentPanel.managedLabel"
                  class="gomoku-player-card__tag"
                  :class="opponentPanel.managedBadgeClass"
                >
                  {{ opponentPanel.managedLabel }}
                </span>
                <span v-if="opponentPanel.isAi" class="gomoku-player-card__tag gomoku-player-card__tag--ai">
                  AI
                </span>
              </div>
            </div>
            <div v-if="opponentPanel.isCurrentTurn" class="gomoku-player-card__timer">
              <TurnCountdown
                :seconds="turnTimeoutSeconds"
                :expires-at-ms="turnDeadlineAtMs"
                compact
              />
            </div>
          </article>
        </div>

        <div class="gomoku-board-area">
          <div v-if="gameViewVersion > 0" class="gomoku-board-wrap">
            <GomokuBoard
              :board="boardMatrix"
              :board-size="boardSize"
              :last-place-row="lastPlaceRow"
              :last-place-col="lastPlaceCol"
              :current-stone="viewerStone"
              :disabled="boardDisabled"
              :interactive="boardInteractive"
              @cell-click="handleCellClick"
            />
          </div>
          <p v-else class="empty-text">正在加载对局…</p>

          <div v-if="gameViewVersion > 0" class="gomoku-board-actions">
            <button
              v-if="hasRequestUndo || hasPendingOwnUndoRequest"
              type="button"
              class="game-action-btn game-action-btn--ghost game-action-btn--sm"
              :disabled="actionDisabled || hasPendingOwnUndoRequest"
              @click="submitByActionType('REQUEST_UNDO')"
            >
              {{ hasPendingOwnUndoRequest ? '申请悔棋（已发送）' : '申请悔棋' }}
            </button>
            <button
              v-if="hasResign"
              type="button"
              class="game-action-btn game-action-btn--ghost game-action-btn--sm"
              :disabled="actionDisabled"
              @click="submitByActionType('RESIGN')"
            >
              认输
            </button>
            <button
              v-if="!viewerManagedActive"
              type="button"
              class="game-action-btn game-action-btn--ghost game-action-btn--sm"
              :disabled="gameViewActionBusy"
              @click="onStartManagedMode"
            >
              托管
            </button>
            <button
              v-else
              type="button"
              class="game-action-btn game-action-btn--ghost game-action-btn--sm"
              :disabled="gameViewActionBusy"
              @click="onStopManagedMode"
            >
              取消托管
            </button>
          </div>
        </div>

        <div v-if="selfPanel" class="gomoku-self-panel">
          <article
            class="gomoku-player-card"
            :class="{ 'gomoku-player-card--active': selfPanel.isCurrentTurn }"
          >
            <div class="gomoku-player-card__avatar">
              <img
                v-if="selfPanel.avatar"
                :src="selfPanel.avatar"
                :alt="selfPanel.nickname"
              />
              <span v-else aria-hidden="true">{{ selfPanel.avatarInitial }}</span>
            </div>
            <div class="gomoku-player-card__main">
              <h3 class="gomoku-player-card__name" :title="selfPanel.nickname">
                {{ selfPanel.nickname }}
              </h3>
              <div v-if="selfPanel.stoneTone" class="gomoku-player-card__stone">
                <span class="gomoku-stone-indicator" :class="selfPanel.stoneTone" />
              </div>
              <div
                v-if="selfPanel.isAi || selfPanel.managedLabel"
                class="gomoku-player-card__tags"
              >
                <span
                  v-if="selfPanel.managedLabel"
                  class="gomoku-player-card__tag"
                  :class="selfPanel.managedBadgeClass"
                >
                  {{ selfPanel.managedLabel }}
                </span>
                <span v-if="selfPanel.isAi" class="gomoku-player-card__tag gomoku-player-card__tag--ai">
                  AI
                </span>
              </div>
            </div>
            <div v-if="selfPanel.isCurrentTurn" class="gomoku-player-card__timer">
              <TurnCountdown
                :seconds="turnTimeoutSeconds"
                :expires-at-ms="turnDeadlineAtMs"
                compact
              />
            </div>
          </article>
        </div>
      </div>
    </div>

    <GomokuSettlementDialog
      :visible="settlementVisible"
      :winner-player-id="gameState.winnerPlayerId"
      :winner-stone="gameState.winnerStone"
      :finish-reason="gameState.finishReason"
      :moves-count="gameState.movesCount"
      :members="currentRoom?.members || []"
      @close="onSettlementClose"
      @lobby="onSettlementLobby"
    />
    <AppModal
      :visible="hasPendingIncomingUndoRequest"
      title="悔棋请求"
      :closable="false"
      :mask-closable="false"
    >
      <p class="muted-small">对手请求悔棋，是否同意？</p>
      <template #footer>
        <div class="room-hub-form__actions">
          <button
            type="button"
            class="game-action-btn game-action-btn--ghost game-action-btn--sm"
            :disabled="actionDisabled"
            @click="rejectUndoRequest"
          >
            拒绝
          </button>
          <button
            type="button"
            class="game-action-btn game-action-btn--primary game-action-btn--sm"
            :disabled="actionDisabled"
            @click="acceptUndoRequest"
          >
            同意
          </button>
        </div>
      </template>
    </AppModal>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { TurnCountdown } from '../../components/game/index.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import { useRoomStore } from '../../stores/roomStore.js';
import { useStrategyTurnGameView } from '../../composables/useStrategyTurnGameView.js';
import * as roomService from '../../services/roomService.js';
import * as strategyTurnGameViewService from '../../services/strategyTurnGameViewService.js';
import { canFetchRemote } from '../../services/remoteGate.js';
import AppModal from '../../components/AppModal.vue';
import GomokuBoard from './components/GomokuBoard.vue';
import GomokuSettlementDialog from './components/GomokuSettlementDialog.vue';
import './gomokuPage.css';

const GOMOKU_CODE = 'gomoku';

const route = useRoute();
const router = useRouter();
const platform = usePlatformStore();
const roomStore = useRoomStore();
const { currentRoom } = storeToRefs(roomStore);

const {
  version: gameViewVersion,
  viewerPlayerId,
  currentPlayerId,
  isGameOver: gameViewIsGameOver,
  publicState: gameViewPublicState,
  legalActions: gameViewLegalActions,
  playbackBusy: gameViewPlaybackBusy
} = useStrategyTurnGameView();

const loading = ref(false);
const loadError = ref('');
const gameViewLoadError = ref('');
const gameViewActionBusy = ref(false);
const shellRejoinOffered = ref(false);
const rejoinBusy = ref(false);
const settlementVisible = ref(false);
const settlementDismissed = ref(false);

/** @type {(() => void)|null} */
let releaseRoomRealtime = null;
/** @type {(() => void)|null} */
let releaseRoomPresence = null;

const activeRoomId = computed(() => String(route.params.roomId || '').trim());
const activeGameCode = computed(() => String(route.params.gameCode || '').trim() || GOMOKU_CODE);
const onlineBlocked = computed(() => !canFetchRemote());
const currentPlayerIdLocal = computed(() => roomService.getCurrentPlayerId());

const gameState = computed(() => gameViewPublicState.value?.gameState || {});
const boardMatrix = computed(() => {
  const board = gameState.value.board;
  return Array.isArray(board) ? board : [];
});
const boardSize = computed(() => Number(gameState.value.boardSize) || 15);
const lastPlaceRow = computed(() => gameState.value.lastPlaceRow);
const lastPlaceCol = computed(() => gameState.value.lastPlaceCol);
const turnDeadlineAtMs = computed(() => Number(gameState.value.currentTurnDeadlineAt) || null);
const turnTimeoutSeconds = computed(() => {
  const started = Number(gameState.value.currentTurnStartedAt) || 0;
  const deadline = Number(gameState.value.currentTurnDeadlineAt) || 0;
  if (!started || !deadline || deadline <= started) {
    return 30;
  }
  return Math.max(1, Math.round((deadline - started) / 1000));
});

const viewerRoomMember = computed(() => {
  const viewerId = viewerPlayerId.value;
  const members = currentRoom.value?.members;
  if (!viewerId || !Array.isArray(members)) {
    return null;
  }
  return (
    members.find((item) => String(item?.playerId || '').trim() === String(viewerId).trim()) || null
  );
});
const viewerManagedActive = computed(
  () => String(viewerRoomMember.value?.managedMode || '').trim() === 'active'
);

/**
 * @param {object|null|undefined} room
 * @returns {boolean}
 */
function isUserInRoom(room) {
  const playerId = currentPlayerIdLocal.value;
  if (!playerId || !room?.members) {
    return false;
  }
  return room.members.some((item) => {
    const samePlayer = String(item?.playerId || '').trim() === playerId;
    return samePlayer && String(item?.managedMode || '').trim() !== 'shell';
  });
}

/**
 * @param {object|null|undefined} room
 * @returns {boolean}
 */
function isUserShellInRoom(room) {
  const playerId = currentPlayerIdLocal.value;
  if (!playerId || !room?.members) {
    return false;
  }
  return room.members.some((item) => {
    const samePlayer = String(item?.playerId || '').trim() === playerId;
    return samePlayer && String(item?.managedMode || '').trim() === 'shell';
  });
}

const isRoomMember = computed(() => isUserInRoom(currentRoom.value));
const canShowGameView = computed(() => {
  if (onlineBlocked.value || loading.value) {
    return false;
  }
  if (!currentRoom.value || !isRoomMember.value) {
    return false;
  }
  const status = String(currentRoom.value.status || '').trim();
  if (status === 'playing') {
    return true;
  }
  return gameViewIsGameOver.value && !settlementDismissed.value;
});

const playRoomLabel = computed(() => {
  const name = String(currentRoom.value?.roomName || '').trim();
  return name || '五子棋对局';
});

/**
 * @param {string} playerId
 * @returns {string}
 */
function resolvePlayerNickname(playerId) {
  const members = currentRoom.value?.members;
  if (!Array.isArray(members)) {
    return playerId;
  }
  const matched = members.find((item) => String(item?.playerId || '').trim() === playerId);
  return String(matched?.nickname || '').trim() || playerId;
}

/**
 * @param {object|null|undefined} member
 * @returns {string}
 */
function resolveManagedLabel(member) {
  const managedMode = String(member?.managedMode || '').trim();
  if (managedMode === 'active') {
    return '托管中';
  }
  if (managedMode === 'shell') {
    return '离线托管';
  }
  return '';
}

/**
 * @param {object|null|undefined} member
 * @returns {string}
 */
function resolveManagedClass(member) {
  const managedMode = String(member?.managedMode || '').trim();
  if (managedMode === 'active') {
    return 'managed-active';
  }
  if (managedMode === 'shell') {
    return 'managed-shell';
  }
  return '';
}

/**
 * @param {string} nickname
 * @returns {string}
 */
function resolveAvatarInitial(nickname) {
  const name = String(nickname || '').trim();
  return name ? name.charAt(0) : '?';
}

/**
 * @param {string} stone
 * @returns {string}
 */
function stoneToTone(stone) {
  const normalized = String(stone || '').toUpperCase();
  if (normalized === 'WHITE') {
    return 'white';
  }
  if (normalized === 'BLACK') {
    return 'black';
  }
  return '';
}

/**
 * @param {object} playerState
 * @param {string} playerId
 * @returns {object}
 */
function buildPanel(playerState, playerId) {
  const members = currentRoom.value?.members;
  const member = Array.isArray(members)
    ? members.find((item) => String(item?.playerId || '').trim() === playerId)
    : null;
  const nickname = resolvePlayerNickname(playerId);
  const managedMode = String(member?.managedMode || '').trim();
  const isManagedMode = ['active', 'shell'].includes(managedMode);
  return {
    playerId,
    nickname,
    avatar: String(member?.avatar || '').trim(),
    avatarInitial: resolveAvatarInitial(nickname),
    stoneTone: stoneToTone(playerState?.stone),
    isAi: Boolean(member?.isAi),
    isManaged: isManagedMode,
    managedLabel: resolveManagedLabel(member),
    managedBadgeClass: resolveManagedClass(member),
    isCurrentTurn: playerId === String(currentPlayerId.value || '').trim()
  };
}

const selfPanel = computed(() => {
  const viewerId = String(viewerPlayerId.value || '').trim();
  const players = gameViewPublicState.value?.players;
  if (!viewerId || !Array.isArray(players)) {
    return null;
  }
  const playerState = players.find((item) => String(item?.playerId || '').trim() === viewerId);
  if (!playerState) {
    return null;
  }
  return buildPanel(playerState, viewerId);
});

const opponentPanel = computed(() => {
  const viewerId = String(viewerPlayerId.value || '').trim();
  const players = gameViewPublicState.value?.players;
  if (!viewerId || !Array.isArray(players)) {
    return null;
  }
  const playerState = players.find((item) => String(item?.playerId || '').trim() !== viewerId);
  if (!playerState) {
    return null;
  }
  const playerId = String(playerState.playerId || '').trim();
  return buildPanel(playerState, playerId);
});

const viewerStone = computed(() => {
  const viewerId = String(viewerPlayerId.value || '').trim();
  const players = gameViewPublicState.value?.players;
  if (!viewerId || !Array.isArray(players)) {
    return 'BLACK';
  }
  const matched = players.find((item) => String(item?.playerId || '').trim() === viewerId);
  return String(matched?.stone || 'BLACK');
});

const viewerIsCurrentTurn = computed(
  () => String(currentPlayerId.value || '').trim() === String(viewerPlayerId.value || '').trim()
);

const boardInteractive = computed(
  () => viewerIsCurrentTurn.value && !viewerManagedActive.value && !gameViewIsGameOver.value
);

const boardDisabled = computed(
  () =>
    gameViewActionBusy.value ||
    gameViewPlaybackBusy.value ||
    !canShowGameView.value ||
    gameViewIsGameOver.value
);

const actionDisabled = computed(
  () => boardDisabled.value || viewerManagedActive.value
);

const hasRequestUndo = computed(() =>
  (gameViewLegalActions.value || []).some((item) => item.actionType === 'REQUEST_UNDO')
);

const hasResign = computed(() =>
  (gameViewLegalActions.value || []).some((item) => item.actionType === 'RESIGN')
);

const hasPendingOwnUndoRequest = computed(() => {
  const undoRequest = gameState.value.undoRequest;
  if (!undoRequest) {
    return false;
  }
  return String(undoRequest.requesterPlayerId || '').trim() === String(viewerPlayerId.value || '').trim();
});

const hasPendingIncomingUndoRequest = computed(() => {
  const undoRequest = gameState.value.undoRequest;
  if (!undoRequest) {
    return false;
  }
  return String(undoRequest.targetPlayerId || '').trim() === String(viewerPlayerId.value || '').trim();
});

/**
 * @param {number} row
 * @param {number} col
 * @returns {object|undefined}
 */
function findPlaceAction(row, col) {
  return (gameViewLegalActions.value || []).find((action) => {
    return (
      action.actionType === 'PLACE_STONE' &&
      action.selection?.type === 'BOARD_CELL' &&
      Number(action.selection?.config?.row) === row &&
      Number(action.selection?.config?.col) === col
    );
  });
}

/**
 * @param {string} actionType
 * @returns {string}
 */
function findActionIdByType(actionType) {
  const action = (gameViewLegalActions.value || []).find(
    (item) => item.actionType === actionType
  );
  return String(action?.actionId || '').trim();
}

/**
 * @param {string} actionId
 */
async function submitGameAction(actionId) {
  const normalized = String(actionId || '').trim();
  if (!normalized) {
    return;
  }
  const roomId = activeRoomId.value;
  if (!roomId || actionDisabled.value) {
    return;
  }
  const baseVersion = strategyTurnGameViewService.getCurrentGameViewVersion();
  if (!baseVersion) {
    gameViewLoadError.value = '对局视图尚未就绪';
    return;
  }
  gameViewActionBusy.value = true;
  gameViewLoadError.value = '';
  try {
    await roomService.applyRoomGameAction(roomId, {
      actionId: normalized,
      baseVersion,
      clientSeq: Date.now()
    });
  } catch (err) {
    gameViewLoadError.value = err?.message || '操作失败';
  } finally {
    gameViewActionBusy.value = false;
  }
}

/**
 * @param {string} actionType
 */
async function submitByActionType(actionType) {
  const actionId = findActionIdByType(actionType);
  if (!actionId) {
    return;
  }
  await submitGameAction(actionId);
}

async function acceptUndoRequest() {
  await submitByActionType('ACCEPT_UNDO');
}

async function rejectUndoRequest() {
  await submitByActionType('REJECT_UNDO');
}

/**
 * @param {number} row
 * @param {number} col
 */
async function handleCellClick(row, col) {
  const action = findPlaceAction(row, col);
  if (!action) {
    return;
  }
  await submitGameAction(action.actionId);
}

async function backToRoomOrLobby() {
  const roomId = activeRoomId.value;
  const gameCode = activeGameCode.value;
  if (roomId) {
    await router.push({ name: 'online-room-waiting', params: { gameCode, roomId } });
    return;
  }
  await router.push({ name: 'online-room-list', params: { gameCode } });
}

async function onExitRoomWithShell() {
  const roomId = activeRoomId.value;
  if (!roomId) {
    await onBackToLobby();
    return;
  }
  gameViewActionBusy.value = true;
  try {
    await roomService.leaveRoom(roomId);
    roomService.resetRoomGameView();
    await onBackToLobby();
  } catch (err) {
    gameViewLoadError.value = err?.message || '退出房间失败';
  } finally {
    gameViewActionBusy.value = false;
  }
}

async function onRejoinRoom() {
  const roomId = activeRoomId.value;
  if (!roomId || rejoinBusy.value) {
    return;
  }
  rejoinBusy.value = true;
  gameViewLoadError.value = '';
  try {
    await roomService.rejoinManagedRoom(roomId);
    shellRejoinOffered.value = false;
    await roomService.loadRoomGameView(roomId);
  } catch (err) {
    gameViewLoadError.value = err?.message || '重新加入失败';
  } finally {
    rejoinBusy.value = false;
  }
}

async function onBackToLobby() {
  roomService.resetRoomGameView();
  await router.push({ name: 'online-room-list', params: { gameCode: activeGameCode.value } });
}

async function onStartManagedMode() {
  const roomId = activeRoomId.value;
  if (!roomId || viewerManagedActive.value) {
    return;
  }
  gameViewActionBusy.value = true;
  try {
    await roomService.startManagedMode(roomId);
  } catch (err) {
    gameViewLoadError.value = err?.message || '开启托管失败';
  } finally {
    gameViewActionBusy.value = false;
  }
}

async function onStopManagedMode() {
  const roomId = activeRoomId.value;
  if (!roomId || !viewerManagedActive.value) {
    return;
  }
  gameViewActionBusy.value = true;
  try {
    await roomService.stopManagedMode(roomId);
  } catch (err) {
    gameViewLoadError.value = err?.message || '取消托管失败';
  } finally {
    gameViewActionBusy.value = false;
  }
}

function onSettlementClose() {
  settlementVisible.value = false;
  settlementDismissed.value = true;
  roomService.resetRoomGameView();
  void backToRoomOrLobby();
}

function onSettlementLobby() {
  settlementVisible.value = false;
  settlementDismissed.value = true;
  roomService.resetRoomGameView();
  void router.push({ path: '/' });
}

async function ensureRoomAndGameView() {
  const roomId = activeRoomId.value;
  if (!roomId || onlineBlocked.value) {
    return;
  }
  loading.value = true;
  loadError.value = '';
  gameViewLoadError.value = '';
  try {
    await roomService.loadRoomDetail(roomId);
    if (!currentRoom.value) {
      loadError.value = '房间不存在或已被删除';
      await backToRoomOrLobby();
      return;
    }
    if (!isRoomMember.value) {
      if (isUserShellInRoom(currentRoom.value)) {
        shellRejoinOffered.value = true;
        return;
      }
      loadError.value = '你尚未加入该房间';
      await backToRoomOrLobby();
      return;
    }
    shellRejoinOffered.value = false;
    const status = String(currentRoom.value.status || '').trim();
    strategyTurnGameViewService.setActiveRoom(roomId, GOMOKU_CODE);
    if (status === 'playing' && !gameViewVersion.value) {
      await roomService.loadRoomGameView(roomId);
    }
  } catch (err) {
    gameViewLoadError.value = err?.message || '加载对局失败';
  } finally {
    loading.value = false;
  }
}

watch(
  () => [gameViewIsGameOver.value, gameViewVersion.value, gameViewPlaybackBusy.value],
  ([isOver, version, playbackBusy]) => {
    if (!isOver || !version || playbackBusy || settlementDismissed.value) {
      return;
    }
    settlementVisible.value = true;
  }
);

onMounted(async () => {
  platform.setCurrentGame(activeGameCode.value);
  if (onlineBlocked.value) {
    return;
  }
  const roomId = activeRoomId.value;
  if (!roomId) {
    await backToRoomOrLobby();
    return;
  }
  releaseRoomRealtime = roomService.bindRoomRealtime(roomId);
  releaseRoomPresence = roomService.bindRoomPresencePong(
    roomId,
    activeGameCode.value,
    () => String(route.params.roomId || '').trim() === roomId
  );
  await ensureRoomAndGameView();
});

onUnmounted(() => {
  if (releaseRoomRealtime) {
    releaseRoomRealtime();
    releaseRoomRealtime = null;
  }
  if (releaseRoomPresence) {
    releaseRoomPresence();
    releaseRoomPresence = null;
  }
  roomService.resetRoomGameView();
});
</script>
