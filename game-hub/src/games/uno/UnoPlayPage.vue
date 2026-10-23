<template>
  <div class="uno-page">
    <p v-if="loading" class="empty-text uno-page__status">正在加载房间与对局信息…</p>
    <p v-else-if="loadError" class="empty-text uno-page__status">{{ loadError }}</p>
    <p v-else-if="gameViewLoadError" class="empty-text uno-page__status">
      {{ gameViewLoadError }}
    </p>

    <div v-else-if="shellRejoinOffered" class="uno-page__status">
      <p class="empty-text">你已退出对局，席位由托管保留。重新加入后可继续对局。</p>
      <div class="uno-page__actions">
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

    <div v-else-if="!canShowGameView" class="uno-page__loading-shell">
      <p class="empty-text">正在校验房间状态…</p>
    </div>

    <StrategyTurnMultiplayerLayout v-else>
      <template #topRoomBar>
<AppPageHeader title="UNO" :aria-label="`UNO · ${playRoomLabel}`">
          <template #actions>
            <button type="button" class="game-action-btn game-action-btn--ghost game-action-btn--sm" @click="backToRoomOrLobby">返回房间</button>
            <AppMenu label="更多操作" :items="[
              { id: 'manage', label: viewerManagedActive ? '取消托管' : '托管', icon: 'pause', disabled: gameViewActionBusy || !canShowGameView },
              { id: 'exit', label: '退出并托管', icon: 'logout', danger: true }
            ]" @select="onPlayMenuSelect" />
          </template>
        </AppPageHeader>
      </template>

      <template #leftPlayers>
        <div class="uno-page__players">
          <TurnPlayerPanel
            v-for="player in leftPlayerPanels"
            :key="player.playerId"
            layout="edge-left"
            :nickname="player.nickname"
            :hand-count="player.handCount"
            :is-ai="player.isAi"
            :managed-label="player.managedLabel"
            :managed-badge-class="player.managedBadgeClass"
            :is-current-turn="player.isCurrentTurn"
            :finish-rank="player.finishRank"
            :show-countdown="player.isCurrentTurn && !gameViewIsGameOver"
            :countdown-seconds="turnTimeoutSeconds"
            :countdown-expires-at-ms="player.isCurrentTurn ? turnDeadlineAtMs : null"
            low-hand-count-label="UNO"
          >
            <template #action-display>
              <UnoPlayerActionDisplay
                v-if="playerActionMap[player.playerId]"
                :view-model="playerActionMap[player.playerId]"
              />
            </template>
          </TurnPlayerPanel>
        </div>
      </template>

      <template #rightPlayers>
        <div class="uno-page__players">
          <TurnPlayerPanel
            v-for="player in rightPlayerPanels"
            :key="player.playerId"
            layout="edge-right"
            :nickname="player.nickname"
            :hand-count="player.handCount"
            :is-ai="player.isAi"
            :is-managed="player.isManaged"
            :managed-label="player.managedLabel"
            :managed-badge-class="player.managedBadgeClass"
            :is-current-turn="player.isCurrentTurn"
            :finish-rank="player.finishRank"
            :show-countdown="player.isCurrentTurn && !gameViewIsGameOver"
            :countdown-seconds="turnTimeoutSeconds"
            :countdown-expires-at-ms="player.isCurrentTurn ? turnDeadlineAtMs : null"
            low-hand-count-label="UNO"
          >
            <template #action-display>
              <UnoPlayerActionDisplay
                v-if="playerActionMap[player.playerId]"
                :view-model="playerActionMap[player.playerId]"
              />
            </template>
          </TurnPlayerPanel>
        </div>
      </template>

      <template #centerStage>
        <div v-if="gameViewVersion > 0" class="uno-page__center">
          <UnoDiscardArea
            :discard-pile-recent-cards="discardPileRecentCards"
            :current-color="currentColor"
          />
        </div>
        <p v-else class="empty-text">正在加载对局…</p>
      </template>

      <template #bottomActionArea>
        <div class="uno-page__bottom-stack">
          <TurnPlayerPanel class="uno-page__self-player" nickname="你" :hand-count="handCards.length" :is-current-turn="viewerIsCurrentTurn"
            :is-managed="viewerManagedActive" :show-countdown="viewerIsCurrentTurn && !gameViewIsGameOver"
            :countdown-seconds="turnTimeoutSeconds" :countdown-expires-at-ms="turnDeadlineAtMs" low-hand-count-label="UNO" />
          <div class="uno-page__actions">
            <TurnActionBar
              :action-offers="gameViewActionOffers"
              :play-enabled="playActionEnabled"
              :hint-enabled="hintEnabled"
              :disabled="manualActionDisabled"
              :managed-blocked="viewerManagedActive"
              :show-countdown="false"
              @action="onTurnBarAction"
            >
            </TurnActionBar>
          </div>
          <div class="uno-page__hand">
            <div class="uno-page__hand-row">
              <SelectableItemHand
                :items="handItems"
                :selected-item-ids="selectedCardIds"
                :selectable-item-ids="selectableItemIds"
                :disabled-item-ids="disabledItemIds"
                :disabled="interactionDisabled"
                @change="onHandSelectionChange"
              >
                <template #item="{ item }">
                  <UnoCard :card-code="item.cardCode" />
                </template>
              </SelectableItemHand>
            </div>
          </div>
        </div>
      </template>
    </StrategyTurnMultiplayerLayout>

    <UnoSettlementDialog
      :visible="settlementVisible"
      :rankings="settlementRankings"
      :players="settlementPlayers"
      :members="currentRoom?.members || []"
      @close="onSettlementClose"
    />

    <UnoColorPicker
      :visible="colorPickerVisible"
      :disabled="interactionDisabled"
      @select="onColorPicked"
      @cancel="onColorPickerCancel"
    />
  </div>
</template>

<script setup>
import AppPageHeader from '../../components/ui/AppPageHeader.vue';
import AppMenu from '../../components/ui/AppMenu.vue';
import { computed, onMounted, watch } from 'vue';
import { StrategyTurnMultiplayerLayout } from '../../game-templates/strategy-turn-multiplayer/index.js';
import {
  SelectableItemHand,
  TurnActionBar,
  TurnPlayerPanel
} from '../../components/game/index.js';
import { TURN_ACTION_BAR_KEY } from '../../components/game/controls/turnControlEnums.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import * as roomGameService from '../../services/roomGameService.js';
import * as strategyTurnGameViewService from '../../services/strategyTurnGameViewService.js';
import { useStrategyTurnRoomLifecycle } from '../../composables/useStrategyTurnRoomLifecycle.js';
import { useStrategyTurnActionController } from '../../composables/useStrategyTurnActionController.js';
import { useStrategyTurnManagedMode } from '../../composables/useStrategyTurnManagedMode.js';
import UnoCard from './components/UnoCard.vue';
import UnoColorPicker from './components/UnoColorPicker.vue';
import UnoDiscardArea from './components/UnoDiscardArea.vue';
import UnoPlayerActionDisplay from './components/UnoPlayerActionDisplay.vue';
import UnoSettlementDialog from './components/UnoSettlementDialog.vue';
import { useUnoGameView } from './composables/useUnoGameView.js';
import { useStrategyTurnGameView } from '../../composables/useStrategyTurnGameView.js';
import { useUnoCardMatching } from './composables/useUnoCardMatching.js';
import { useUnoHandInteraction } from './composables/useUnoHandInteraction.js';
import { useUnoPlayViewModel } from './composables/useUnoPlayViewModel.js';
import { useUnoTerminalFlow } from './composables/useUnoTerminalFlow.js';
import {
  hasPlayCardOffer
} from './unoActionOffersAdapter.js';
import * as unoService from './unoService.js';
import { applyUnoConfig, UNO_CODE } from './unoConfig.js';

const platform = usePlatformStore();

const {
  version: gameViewVersion,
  viewerPlayerId: gameViewViewerId,
  currentPlayerId: gameViewCurrentPlayerId,
  publicState: gameViewPublicState,
  privateState: gameViewPrivateState,
  actionOffers: gameViewActionOffers,
  playbackBusy: gameViewPlaybackBusy
} = useUnoGameView();

const { isGameOver: gameViewIsGameOver, frameEvents } = useStrategyTurnGameView();

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
  playRoomLabel,
  createCanShowGameView,
  rejoin: onRejoinRoom,
  exitWithShell: onExitRoomWithShell,
  backToRoomOrLobby,
  navigateToLobby
} = useStrategyTurnRoomLifecycle({
  defaultGameCode: UNO_CODE,
  defaultRoomLabel: '对局中',
  loadGameView: unoService.loadRoomGameView
});

const {
  settlementVisible,
  settlementDismissed,
  onSettlementClose
} = useUnoTerminalFlow({
  isGameOverRef: gameViewIsGameOver,
  versionRef: gameViewVersion,
  playbackBusyRef: gameViewPlaybackBusy,
  roomRef: currentRoom,
  roomIdRef: activeRoomId,
  resetGameView: roomGameService.resetRoomGameView,
  navigate: (destination) =>
    destination === 'lobby' ? navigateToLobby() : backToRoomOrLobby()
});

const {
  busy: gameViewActionBusy,
  submitAction
} = useStrategyTurnActionController({
  roomIdRef: activeRoomId,
  readVersion: strategyTurnGameViewService.getCurrentGameViewVersion,
  submit: unoService.applyRoomGameAction,
  reload: unoService.loadRoomGameView,
  errorRef: gameViewLoadError
});

const canShowGameView = createCanShowGameView(gameViewIsGameOver, settlementDismissed);

const {
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
  playerActionMap
} = useUnoPlayViewModel({
  roomIdRef: activeRoomId,
  currentRoomRef: currentRoom,
  publicStateRef: gameViewPublicState,
  privateStateRef: gameViewPrivateState,
  viewerIdRef: gameViewViewerId,
  currentPlayerIdRef: gameViewCurrentPlayerId,
  versionRef: gameViewVersion,
  frameEventsRef: frameEvents,
  isGameOverRef: gameViewIsGameOver,
  playbackBusyRef: gameViewPlaybackBusy,
  actionBusyRef: gameViewActionBusy,
  canShowRef: canShowGameView
});

const {
  selectedCardIds,
  hintCursor,
  matchState,
  selectableItemIds,
  disabledItemIds,
  determinedAction
} = useUnoCardMatching({
  actionOffersRef: gameViewActionOffers,
  handCardsRef: handCards,
  interactionDisabledRef: interactionDisabled
});

const {
  colorPickerVisible,
  selectedWildColorCandidateCount,
  selectCards,
  applyHint,
  openColorPickerIfNeeded: openWildColorPickerIfNeeded,
  cancelColorPicker: onColorPickerCancel,
  chooseColor: resolveColorChoice,
  reset: resetHandInteraction
} = useUnoHandInteraction({
  selectedCardIdsRef: selectedCardIds,
  hintCursorRef: hintCursor,
  matchStateRef: matchState,
  handCardsRef: handCards,
  disabledRef: interactionDisabled
});

const playActionEnabled = computed(() => {
  if (determinedAction.value?.actionId) {
    return true;
  }
  return selectedWildColorCandidateCount.value > 1;
});

const hintEnabled = computed(() => {
  if (interactionDisabled.value) {
    return false;
  }
  return hasPlayCardOffer(gameViewActionOffers.value);
});

watch(gameViewVersion, () => {
  resetHandInteraction();
});

const { start: onStartManagedMode, stop: onStopManagedMode } = useStrategyTurnManagedMode({
  roomIdRef: activeRoomId,
  managedActiveRef: viewerManagedActive,
  busyRef: gameViewActionBusy,
  errorRef: gameViewLoadError
});

/**
 * @param {string[]} ids
 */
function onHandSelectionChange(ids) {
  selectCards(ids);
}

/**
 * @param {{ color: string }} payload
 */
async function onColorPicked(payload) {
  const chooseColor = String(payload?.color || '').trim();
  const action = resolveColorChoice(chooseColor);
  const actionId = String(action?.actionId || '').trim();
  if (!actionId) {
    gameViewLoadError.value = '当前无法打出该牌';
    return;
  }
  selectedCardIds.value = [];
  await submitGameAction('PLAY_CARD', actionId);
}

/**
 * 通过 Adapter Registry 提交 UNO 动作。
 * @param {string} actionType
 * @param {string} actionId
 * @returns {Promise<void>}
 */
async function submitGameAction(actionType, actionId) {
  const type = String(actionType || '').trim();
  const id = String(actionId || '').trim();
  if (!type || !id || interactionDisabled.value) return;
  try {
    await submitAction(gameViewActionOffers.value, type, id);
    resetHandInteraction();
  } catch {
    // ActionController 已记录错误。
  }
}

/**
 * @param {{ barKey: string; actionType: string; options: object[] }} payload
 */
async function onTurnBarAction(payload) {
  if (interactionDisabled.value) {
    return;
  }
  if (payload.barKey === TURN_ACTION_BAR_KEY.UI_ACTION_HINT) {
    applyHint();
    return;
  }

  if (payload.barKey === TURN_ACTION_BAR_KEY.PLAY) {
    if (openWildColorPickerIfNeeded()) {
      return;
    }

    const actionId = String(determinedAction.value?.actionId || '').trim();
    if (!actionId) {
      gameViewLoadError.value = '请先选择可打出的牌';
      return;
    }

    await submitGameAction('PLAY_CARD', actionId);
    return;
  }

  const options = Array.isArray(payload.options) ? payload.options : [];
  const option = options[0];
  const actionId = String(option?.actionId || '').trim();
  const actionType = String(payload.actionType || option?.actionType || '').trim();
  if (!actionId || !actionType) {
    return;
  }
  await submitGameAction(actionType, actionId);
}

onMounted(() => {
  platform.setCurrentGame(activeGameCode.value);
  if (!onlineBlocked.value) {
    try {
      applyUnoConfig();
    } catch {
      // 配置错误由服务层处理。
    }
  }
});

/** Dispatches page menu actions through the existing room lifecycle. */
function onPlayMenuSelect(id) {
  if (id === 'manage') return viewerManagedActive.value ? onStopManagedMode() : onStartManagedMode();
  if (id === 'exit') return onExitRoomWithShell();
}
</script>
