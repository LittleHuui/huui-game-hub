<template>
  <div class="doudizhu-page">
    <p v-if="loading" class="empty-text doudizhu-page__status">正在加载房间与对局信息…</p>
    <p v-else-if="loadError" class="empty-text doudizhu-page__status">{{ loadError }}</p>
    <p v-else-if="gameViewLoadError" class="empty-text doudizhu-page__status">
      {{ gameViewLoadError }}
    </p>

    <div v-else-if="shellRejoinOffered" class="doudizhu-page__status">
      <p class="empty-text">你已退出对局，席位由托管保留。重新加入后可继续对局。</p>
      <div class="doudizhu-page__actions">
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
          @click="navigateToLobby"
        >
          返回大厅
        </button>
      </div>
    </div>

    <div v-else-if="!canShowGameView" class="doudizhu-page__status">
      <p class="empty-text">正在校验房间状态…</p>
    </div>

    <StrategyTurnMultiplayerLayout v-else>
      <template #topRoomBar>
        <div class="doudizhu-page__table-topbar">
          <div class="doudizhu-page__play-bar">
            <button
              type="button"
              class="game-action-btn game-action-btn--ghost game-action-btn--sm"
              @click="onBackToRoom"
            >
              返回房间
            </button>
            <button
              type="button"
              class="game-action-btn game-action-btn--ghost game-action-btn--sm"
              @click="onExitRoomWithShell"
            >
              退出并托管
            </button>
            <button
              v-if="!viewerManagedActive"
              type="button"
              class="game-action-btn game-action-btn--ghost game-action-btn--sm"
              :disabled="gameViewActionBusy || !canShowGameView"
              @click="onStartManagedMode"
            >
              托管
            </button>
            <button
              v-else
              type="button"
              class="game-action-btn game-action-btn--ghost game-action-btn--sm"
              :disabled="gameViewActionBusy || !canShowGameView"
              @click="onStopManagedMode"
            >
              取消托管
            </button>
          </div>
          <DoudizhuRoundCards :game-state="gameState" />
        </div>
      </template>

      <template #leftPlayers>
        <div class="doudizhu-page__players">
          <DoudizhuPlayerPanel
            v-if="leftOpponent"
            :nickname="leftOpponent.nickname"
            :player-state="leftOpponent.playerState"
            :is-current-turn="leftOpponent.isCurrentTurn"
            :is-ai="leftOpponent.isAi"
            :managed-label="leftOpponent.managedLabel"
            :managed-badge-class="leftOpponent.managedBadgeClass"
            :show-countdown="leftOpponent.isCurrentTurn"
            :countdown-seconds="turnTimeoutSeconds"
            :countdown-expires-at-ms="leftOpponent.isCurrentTurn ? turnDeadlineAtMs : null"
            :action-feedback="leftActionFeedback"
            :action-feedback-tone="leftActionFeedbackTone"
            :played-card-displays="leftPlayedCardDisplays"
            :played-combo-label="leftPlayedComboLabel"
            :show-remaining-hand="gameViewIsGameOver"
            layout="left"
          />
        </div>
      </template>

      <template #rightPlayers>
        <div class="doudizhu-page__players">
          <DoudizhuPlayerPanel
            v-if="rightOpponent"
            :nickname="rightOpponent.nickname"
            :player-state="rightOpponent.playerState"
            :is-current-turn="rightOpponent.isCurrentTurn"
            :is-ai="rightOpponent.isAi"
            :managed-label="rightOpponent.managedLabel"
            :managed-badge-class="rightOpponent.managedBadgeClass"
            :show-countdown="rightOpponent.isCurrentTurn"
            :countdown-seconds="turnTimeoutSeconds"
            :countdown-expires-at-ms="rightOpponent.isCurrentTurn ? turnDeadlineAtMs : null"
            :action-feedback="rightActionFeedback"
            :action-feedback-tone="rightActionFeedbackTone"
            :played-card-displays="rightPlayedCardDisplays"
            :played-combo-label="rightPlayedComboLabel"
            :show-remaining-hand="gameViewIsGameOver"
            layout="right"
          />
        </div>
      </template>

      <template #centerStage>
        <div v-if="gameViewVersion > 0" class="doudizhu-page__center" />
        <p v-else class="empty-text">正在加载对局…</p>
      </template>

      <template #bottomActionArea>
        <div class="doudizhu-page__bottom-stack">
          <div class="doudizhu-page__bottom-play">
            <div v-if="bottomPlayedCardDisplays.length" class="doudizhu-page__bottom-play-cards" aria-label="你出牌">
              <DoudizhuCard
                v-for="(display, index) in bottomPlayedCardDisplays"
                :key="display.card.cardInstanceId"
                :card="display.card"
                :assigned-rank-code="display.assignedRankCode"
                :style="{ zIndex: index + 1 }"
              />
              <span v-if="bottomPlayedComboLabel" class="doudizhu-page__bottom-play-label">
                {{ bottomPlayedComboLabel }}
              </span>
            </div>
            <p
              v-else-if="bottomActionFeedback"
              class="doudizhu-page__bottom-action-feedback"
              :class="`doudizhu-page__bottom-action-feedback--${bottomActionFeedbackTone}`"
            >
              {{ bottomActionFeedback }}
            </p>
          </div>
          <DoudizhuActionPanel
            :button-actions="buttonActions"
            :can-play-cards="canPlayCards"
            preview-message=""
            :disabled="manualActionDisabled"
            :busy="gameViewActionBusy"
            :play-enabled="playActionEnabled"
            :hint-enabled="hintEnabled"
            :show-countdown="canTakeActionOffer"
            :countdown-seconds="turnTimeoutSeconds"
            :countdown-expires-at-ms="turnDeadlineAtMs"
            @action="onPanelAction"
            @play="onPlayCards"
            @hint="onHint"
          />
          <div class="doudizhu-page__hand-shell">
            <div class="doudizhu-page__hand-row">
              <DoudizhuHand
                :hand-cards="handCards"
                :selected-item-ids="selectedCardIds"
                :selectable-item-ids="selectableItemIds"
                :disabled-item-ids="disabledItemIds"
                :disabled="handInteractionDisabled"
                :busy="gameViewActionBusy"
                @change="onHandSelectionChange"
              />
            </div>
          </div>
        </div>
      </template>
    </StrategyTurnMultiplayerLayout>

    <DoudizhuTerminalSettlementDialog
      :visible="settlementVisible"
      :settlement="settlementData"
      :terminal-metadata="gameViewTerminalMetadata"
      :members="currentRoom?.members || []"
      :viewer-player-id="gameViewViewerId"
      :can-dismiss="canDismissSettlement"
      @close="onSettlementClose"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue';
import { usePlatformStore } from '../../stores/platformStore.js';
import * as roomGameService from '../../services/roomGameService.js';
import * as strategyTurnGameViewService from '../../services/strategyTurnGameViewService.js';
import { useStrategyTurnGameView } from '../../composables/useStrategyTurnGameView.js';
import { useStrategyTurnActionController } from '../../composables/useStrategyTurnActionController.js';
import { useStrategyTurnManagedMode } from '../../composables/useStrategyTurnManagedMode.js';
import { StrategyTurnMultiplayerLayout } from '../../game-templates/strategy-turn-multiplayer/index.js';
import DoudizhuActionPanel from './components/DoudizhuActionPanel.vue';
import DoudizhuCard from './components/DoudizhuCard.vue';
import DoudizhuHand from './components/DoudizhuHand.vue';
import DoudizhuPlayerPanel from './components/DoudizhuPlayerPanel.vue';
import DoudizhuRoundCards from './components/DoudizhuRoundCards.vue';
import DoudizhuTerminalSettlementDialog from './components/DoudizhuTerminalSettlementDialog.vue';
import { applyDoudizhuConfig, DOUDIZHU_CODE } from './doudizhuConfig.js';
import { useDoudizhuActionOffers } from './composables/useDoudizhuActionOffers.js';
import { useDoudizhuCardSelection } from './composables/useDoudizhuCardSelection.js';
import { useDoudizhuActionPreview } from './composables/useDoudizhuActionPreview.js';
import { useDoudizhuHint } from './composables/useDoudizhuHint.js';
import { useDoudizhuRoomLifecycle } from './composables/useDoudizhuRoomLifecycle.js';
import { useDoudizhuTerminalFlow } from './composables/useDoudizhuTerminalFlow.js';
import { hasPlayCardsOffer } from './doudizhuActionOffersAdapter.js';
import { buildPlayedCardDisplays } from './doudizhuGameViewUtils.js';
import {
  formatDoudizhuActionLabel,
  formatDoudizhuComboLabel,
  resolveDoudizhuActionFeedbackTone
} from './doudizhuDisplayText.js';
import { useDoudizhuTableView } from './composables/useDoudizhuTableView.js';
import * as doudizhuService from './doudizhuService.js';
import './doudizhuPage.css';

const platform = usePlatformStore();

const {
  version: gameViewVersion,
  viewerPlayerId: gameViewViewerId,
  currentPlayerId: gameViewCurrentPlayerId,
  publicState: gameViewPublicState,
  privateState: gameViewPrivateState,
  actionOffers: gameViewActionOffers,
  playbackBusy: gameViewPlaybackBusy,
  isGameOver: gameViewIsGameOver,
  terminalMetadata: gameViewTerminalMetadata
} = useStrategyTurnGameView();

const {
  loading,
  loadError,
  gameViewLoadError,
  shellRejoinOffered,
  rejoinBusy,
  activeRoomId,
  activeGameCode,
  onlineBlocked,
  currentRoom,
  navigateToLobby,
  onRejoinRoom: rejoinRoom,
  onExitRoomWithShell,
  onBackToRoom,
  backToRoomOrLobby,
  createCanShowGameView
} = useDoudizhuRoomLifecycle({ gameCode: DOUDIZHU_CODE });

const {
  busy: gameViewActionBusy,
  submitAction
} = useStrategyTurnActionController({
  roomIdRef: activeRoomId,
  readVersion: strategyTurnGameViewService.getCurrentGameViewVersion,
  submit: doudizhuService.applyRoomGameAction,
  reload: doudizhuService.loadRoomGameView,
  errorRef: gameViewLoadError
});

const settlementData = computed(() => gameViewPublicState.value?.gameState?.settlement || {});

const {
  settlementVisible,
  settlementDismissed,
  canDismissSettlement,
  onSettlementClose
} = useDoudizhuTerminalFlow({
    gameViewIsGameOver,
    gameViewVersion,
    gameViewPlaybackBusy,
    terminalMetadata: gameViewTerminalMetadata,
    currentRoom,
    activeRoomId,
    navigateToWaiting: backToRoomOrLobby,
    navigateToLobby: async () => {
      await navigateToLobby();
    },
    resetGameView: roomGameService.resetRoomGameView
  });

const canShowGameView = createCanShowGameView(gameViewIsGameOver, settlementDismissed);

const {
  gameState,
  turnTimeoutSeconds,
  turnDeadlineAtMs,
  handCards,
  viewerManagedActive,
  leftOpponent,
  rightOpponent,
  lastActionEvent
} = useDoudizhuTableView({
  publicStateRef: gameViewPublicState,
  privateStateRef: gameViewPrivateState,
  currentPlayerIdRef: gameViewCurrentPlayerId,
  viewerIdRef: gameViewViewerId,
  currentRoomRef: currentRoom
});

const systemActionDisabled = computed(
  () =>
    !canShowGameView.value ||
    gameViewActionBusy.value ||
    viewerManagedActive.value
);

const { buttonActions, playCardsCapability, canPlayCards, canTakeAction } = useDoudizhuActionOffers(
  gameViewActionOffers
);

// ActionOffer 是当前玩家可操作性的唯一权威来源；currentPlayerId 只用于展示座位和倒计时。
const canTakeActionOffer = computed(() => !systemActionDisabled.value && canTakeAction.value);
const interactionDisabled = computed(() => systemActionDisabled.value || !canPlayCards.value);
const handInteractionDisabled = interactionDisabled;
const manualActionDisabled = computed(() => !canTakeActionOffer.value);
/**
 * 根据当前座位把动作展示在稳定舞台方位；只用于展示，不参与操作判定。
 * @param {string} rawPlayerId
 * @returns {'left'|'right'|'bottom'|'center'}
 */
function resolveActionPosition(rawPlayerId) {
  const playerId = String(rawPlayerId || '').trim();
  if (!playerId) {
    return 'center';
  }
  if (playerId === String(gameViewViewerId.value || '').trim()) {
    return 'bottom';
  }
  if (playerId === String(leftOpponent.value?.playerId || '').trim()) {
    return 'left';
  }
  if (playerId === String(rightOpponent.value?.playerId || '').trim()) {
    return 'right';
  }
  return 'center';
}

// 出牌记录与非出牌反馈是两条独立的公开状态：服务端在有效出牌后会清除
// lastActionEvent，因此牌组展示必须只依据 lastPlay 字段，不能依赖动作反馈事件。
const lastPlayPosition = computed(() => (
  resolveActionPosition(gameState.value?.lastPlayPlayerId)
));
const lastPlayedCardDisplays = computed(() => buildPlayedCardDisplays(
  gameState.value?.lastPlayCards,
  gameState.value?.lastPlay
));
const lastPlayedComboLabel = computed(() => {
  const comboType = String(gameState.value?.lastPlay?.comboType || '').trim();
  return comboType ? formatDoudizhuComboLabel(comboType) : '';
});
const leftPlayedCardDisplays = computed(() => lastPlayPosition.value === 'left' ? lastPlayedCardDisplays.value : []);
const rightPlayedCardDisplays = computed(() => lastPlayPosition.value === 'right' ? lastPlayedCardDisplays.value : []);
const bottomPlayedCardDisplays = computed(() => lastPlayPosition.value === 'bottom' ? lastPlayedCardDisplays.value : []);
const leftPlayedComboLabel = computed(() => leftPlayedCardDisplays.value.length ? lastPlayedComboLabel.value : '');
const rightPlayedComboLabel = computed(() => rightPlayedCardDisplays.value.length ? lastPlayedComboLabel.value : '');
const bottomPlayedComboLabel = computed(() => bottomPlayedCardDisplays.value.length ? lastPlayedComboLabel.value : '');
const lastActionPosition = computed(() => {
  return resolveActionPosition(lastActionEvent.value?.playerId);
});
const lastActionLabel = computed(() => {
  const actionType = String(lastActionEvent.value?.actionType || '').trim();
  if (!actionType || actionType === 'PLAY_CARDS') {
    return '';
  }
  return formatDoudizhuActionLabel(actionType);
});
const lastActionFeedbackTone = computed(() => (
  resolveDoudizhuActionFeedbackTone(lastActionEvent.value?.actionType)
));
const leftActionFeedback = computed(() => (
  lastActionPosition.value === 'left' ? lastActionLabel.value : ''
));
const rightActionFeedback = computed(() => (
  lastActionPosition.value === 'right' ? lastActionLabel.value : ''
));
const bottomActionFeedback = computed(() => (
  lastActionPosition.value === 'bottom' ? lastActionLabel.value : ''
));
const leftActionFeedbackTone = computed(() => (
  leftActionFeedback.value ? lastActionFeedbackTone.value : 'affirmative'
));
const rightActionFeedbackTone = computed(() => (
  rightActionFeedback.value ? lastActionFeedbackTone.value : 'affirmative'
));
const bottomActionFeedbackTone = computed(() => (
  bottomActionFeedback.value ? lastActionFeedbackTone.value : 'affirmative'
));
const { selectedCardIds, selectableItemIds, disabledItemIds, clearSelection } =
  useDoudizhuCardSelection({
    handCardsRef: handCards,
    capabilityRef: playCardsCapability,
    interactionDisabledRef: interactionDisabled,
    actionOffersRef: gameViewActionOffers
  });

const previewEnabled = computed(
  () =>
    !interactionDisabled.value &&
    Boolean(playCardsCapability.value?.supportsPreview) &&
    selectedCardIds.value.length > 0
);

const { playActionEnabled, invalidatePreview } = useDoudizhuActionPreview({
  roomIdRef: activeRoomId,
  gameViewVersionRef: gameViewVersion,
  selectedCardIdsRef: selectedCardIds,
  previewEnabledRef: previewEnabled
});

const hintEnabled = computed(() => {
  if (systemActionDisabled.value || !canPlayCards.value) {
    return false;
  }
  const capability = playCardsCapability.value;
  return Boolean(capability?.supportsSuggestions) && hasPlayCardsOffer(gameViewActionOffers.value);
});

const { requestHint, clearHintCursor } = useDoudizhuHint({
  roomIdRef: activeRoomId,
  gameViewVersionRef: gameViewVersion,
  currentPlayerIdRef: gameViewCurrentPlayerId,
  viewerPlayerIdRef: gameViewViewerId,
  hintEnabledRef: hintEnabled,
  applySelection: (cardInstanceIds) => {
    selectedCardIds.value = [...cardInstanceIds];
  }
});

/**
 * 取消当前交互请求和动画后重新加入房间。
 * @returns {Promise<void>}
 */
async function onRejoinRoom() {
  invalidatePreview();
  clearHintCursor();
  strategyTurnGameViewService.cancelGameViewPlayback();
  await rejoinRoom();
}

/**
 * 仅在出牌语义实际变化时重置本地选牌。
 *
 * GameView 的 version 会随其他玩家操作推进；它本身不代表当前玩家的手牌、
 * 出牌约束或回合发生了变化。将 version 直接作为重置条件会打断同一回合内的
 * 连续选牌，尤其是在上一轮两家均不出、出牌权回到领出玩家的场景。
 */
const playSelectionContextSignature = computed(() => {
  const currentState = gameState.value || {};
  const lastPlay = currentState.lastPlay || {};
  const cardIds = (handCards.value || [])
    .map((card) => String(card?.cardInstanceId || '').trim())
    .filter(Boolean)
    .sort();
  return JSON.stringify({
    roomId: String(activeRoomId.value || '').trim(),
    viewerPlayerId: String(gameViewViewerId.value || '').trim(),
    phase: String(currentState.phase || '').trim(),
    currentPlayerId: String(gameViewCurrentPlayerId.value || '').trim(),
    canPlayCards: Boolean(canPlayCards.value),
    handCardIds: cardIds,
    lastPlay: {
      comboType: String(lastPlay.comboType || '').trim(),
      mainRankValue: Number(lastPlay.mainRankValue) || 0,
      cardCount: Number(lastPlay.cardCount) || 0,
      chainLength: Number(lastPlay.chainLength) || 0
    },
    laizi: {
      enabled: Boolean(currentState.enableLaizi),
      rankCode: String(currentState.laiziRankCode || '').trim()
    }
  });
});

watch(playSelectionContextSignature, (nextSignature, previousSignature) => {
  if (nextSignature === previousSignature) {
    return;
  }
  clearSelection();
  clearHintCursor();
  invalidatePreview();
});

const { start: onStartManagedMode, stop: onStopManagedMode } = useStrategyTurnManagedMode({
  roomIdRef: activeRoomId,
  managedActiveRef: viewerManagedActive,
  busyRef: gameViewActionBusy,
  errorRef: gameViewLoadError
});

/**
 * @param {{ actionType: string; actionId: string }} action
 */
async function onPanelAction(action) {
  const actionType = String(action?.actionType || '').trim();
  const actionId = String(action?.actionId || '').trim();
  if (!actionType || !actionId || manualActionDisabled.value) {
    return;
  }
  await submitEnumeratedAction(actionType, actionId);
}

async function onPlayCards() {
  if (manualActionDisabled.value || !playActionEnabled.value) {
    return;
  }
  const cardInstanceIds = (selectedCardIds.value || [])
    .map((id) => String(id || '').trim())
    .filter(Boolean);
  if (!cardInstanceIds.length) {
    gameViewLoadError.value = '请先选择可出的牌';
    return;
  }
  await submitComposedPlayCards(cardInstanceIds);
}

async function onHint() {
  if (systemActionDisabled.value || !hintEnabled.value) {
    return;
  }
  await requestHint();
}

/**
 * 清理选牌、Hint 游标和 Preview 请求。
 * @returns {void}
 */
function clearInteractionState() {
  clearSelection();
  clearHintCursor();
  invalidatePreview();
}

/**
 * 通过 Registry Adapter 提交斗地主枚举动作。
 * @param {string} actionType
 * @param {string} actionId
 * @returns {Promise<void>}
 */
async function submitEnumeratedAction(actionType, actionId) {
  try {
    await submitAction(gameViewActionOffers.value, actionType, actionId);
    clearInteractionState();
  } catch {
    // ActionController 已记录错误。
  }
}

/**
 * 通过 Registry Adapter 提交斗地主出牌。
 * @param {string[]} cardInstanceIds
 * @returns {Promise<void>}
 */
async function submitComposedPlayCards(cardInstanceIds) {
  try {
    await submitAction(gameViewActionOffers.value, 'PLAY_CARDS', { cardInstanceIds });
    clearInteractionState();
  } catch {
    // ActionController 已记录错误。
  }
}

/**
 * @param {string[]} ids
 */
function onHandSelectionChange(ids) {
  if (interactionDisabled.value) {
    return;
  }
  selectedCardIds.value = Array.isArray(ids) ? [...ids] : [];
}

onMounted(() => {
  platform.setCurrentGame(activeGameCode.value);
  if (!onlineBlocked.value) {
    try {
      applyDoudizhuConfig();
    } catch {
      // 配置错误在 service 内部处理
    }
  }
});

</script>
