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
              @click="requestUndo"
            >
              {{ hasPendingOwnUndoRequest ? '申请悔棋（已发送）' : '申请悔棋' }}
            </button>
            <button
              v-if="hasResign"
              type="button"
              class="game-action-btn game-action-btn--ghost game-action-btn--sm"
              :disabled="actionDisabled"
              @click="resign"
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
      :visible="hasActiveIncomingUndoRequest"
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
import { computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { TurnCountdown } from '../../components/game/index.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import { useStrategyTurnGameView } from '../../composables/useStrategyTurnGameView.js';
import { useStrategyTurnRoomLifecycle } from '../../composables/useStrategyTurnRoomLifecycle.js';
import { useStrategyTurnActionController } from '../../composables/useStrategyTurnActionController.js';
import { useStrategyTurnManagedMode } from '../../composables/useStrategyTurnManagedMode.js';
import { useStrategyTurnTerminalFlow } from '../../composables/useStrategyTurnTerminalFlow.js';
import * as roomGameService from '../../services/roomGameService.js';
import * as strategyTurnGameViewService from '../../services/strategyTurnGameViewService.js';
import AppModal from '../../components/AppModal.vue';
import GomokuBoard from './components/GomokuBoard.vue';
import GomokuSettlementDialog from './components/GomokuSettlementDialog.vue';
import { useGomokuInteraction } from './composables/useGomokuInteraction.js';
import { useGomokuPlayViewModel } from './composables/useGomokuPlayViewModel.js';
import { useGomokuUndoRequestExpiry } from './composables/useGomokuUndoRequestExpiry.js';
import './gomokuPage.css';

const GOMOKU_CODE = 'gomoku';

const router = useRouter();
const platform = usePlatformStore();

const {
  version: gameViewVersion,
  viewerPlayerId,
  currentPlayerId,
  isGameOver: gameViewIsGameOver,
  publicState: gameViewPublicState,
  actionOffers: gameViewActionOffers,
  playbackBusy: gameViewPlaybackBusy
} = useStrategyTurnGameView();

const {
  loading,
  loadError,
  gameViewLoadError,
  shellRejoinOffered,
  rejoinBusy,
  activeRoomId,
  activeGameCode,
  currentRoom,
  createCanShowGameView,
  rejoin: onRejoinRoom,
  exitWithShell: onExitRoomWithShell,
  backToRoomOrLobby,
  navigateToLobby: onBackToLobby
} = useStrategyTurnRoomLifecycle({
  defaultGameCode: GOMOKU_CODE,
  defaultRoomLabel: '五子棋对局',
  loadGameView: roomGameService.loadRoomGameView
});

const {
  visible: settlementVisible,
  dismissed: settlementDismissed,
  close: onSettlementClose,
  navigateOnce: navigateTerminalOnce
} = useStrategyTurnTerminalFlow({
  isGameOverRef: gameViewIsGameOver,
  versionRef: gameViewVersion,
  playbackBusyRef: gameViewPlaybackBusy,
  roomRef: currentRoom,
  roomIdRef: activeRoomId,
  resetGameView: roomGameService.resetRoomGameView,
  navigate: (destination) =>
    destination === 'home' ? router.push({ path: '/' }) : backToRoomOrLobby()
});

const {
  busy: gameViewActionBusy,
  submitAction,
  reset: resetActionController
} = useStrategyTurnActionController({
  roomIdRef: activeRoomId,
  readVersion: strategyTurnGameViewService.getCurrentGameViewVersion,
  submit: roomGameService.applyRoomGameAction,
  reload: roomGameService.loadRoomGameView,
  errorRef: gameViewLoadError
});

const canShowGameView = createCanShowGameView(gameViewIsGameOver, settlementDismissed);

const playRoomLabel = computed(() => {
  const name = String(currentRoom.value?.roomName || '').trim();
  return name || '五子棋对局';
});

const {
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
  boardInteractive,
  boardDisabled,
  actionDisabled,
  hasPendingOwnUndoRequest
} = useGomokuPlayViewModel({
  currentRoomRef: currentRoom,
  publicStateRef: gameViewPublicState,
  actionOffersRef: gameViewActionOffers,
  viewerIdRef: viewerPlayerId,
  currentPlayerIdRef: currentPlayerId,
  isGameOverRef: gameViewIsGameOver,
  playbackBusyRef: gameViewPlaybackBusy,
  actionBusyRef: gameViewActionBusy,
  canShowRef: canShowGameView
});

/**
 * 通过 Adapter Registry 提交五子棋动作。
 * @param {string} actionType
 * @param {string} actionId
 * @returns {Promise<void>}
 */
async function submitGameAction(actionType, actionId) {
  const type = String(actionType || '').trim();
  const id = String(actionId || '').trim();
  if (!type || !id || actionDisabled.value) return;
  try {
    await submitAction(gameViewActionOffers.value, type, id);
  } catch {
    // ActionController 已记录错误。
  }
}

/**
 * 在悔棋请求到期后读取权威 GameView，避免本地继续展示失效请求。
 * @param {{ signal?: AbortSignal }} options
 * @returns {Promise<void>}
 */
async function reloadGameViewAfterUndoExpiry(options) {
  const roomId = activeRoomId.value;
  if (!roomId) {
    return;
  }
  await roomGameService.loadRoomGameView(roomId, options);
}

const {
  hasRequestUndo,
  hasResign,
  requestUndo,
  placeStone: handleCellClick,
  acceptUndo: acceptUndoRequest,
  rejectUndo: rejectUndoRequest,
  resign
} = useGomokuInteraction({
  actionOffersRef: gameViewActionOffers,
  disabledRef: actionDisabled,
  submit: submitGameAction
});

const {
  hasActiveIncomingUndoRequest,
  reset: resetUndoRequestExpiry
} = useGomokuUndoRequestExpiry({
  undoRequestRef: computed(() => gameState.value.undoRequest),
  viewerIdRef: viewerPlayerId,
  reload: reloadGameViewAfterUndoExpiry
});

const { start: onStartManagedMode, stop: onStopManagedMode } = useStrategyTurnManagedMode({
  roomIdRef: activeRoomId,
  managedActiveRef: viewerManagedActive,
  busyRef: gameViewActionBusy,
  errorRef: gameViewLoadError,
  clearErrorOnRequest: false
});

/**
 * 从终局弹窗返回首页，且保证只导航一次。
 * @returns {Promise<void>}
 */
function onSettlementLobby() {
  return navigateTerminalOnce('home');
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

onMounted(() => {
  platform.setCurrentGame(activeGameCode.value);
});

onUnmounted(() => {
  resetActionController();
  resetUndoRequestExpiry();
});
</script>
