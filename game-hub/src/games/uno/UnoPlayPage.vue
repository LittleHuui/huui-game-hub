<template>
  <div class="uno-page">
    <p v-if="loading" class="empty-text uno-page__status">正在加载房间与对局信息…</p>
    <p v-else-if="loadError" class="empty-text uno-page__status">{{ loadError }}</p>
    <p v-else-if="gameViewLoadError" class="empty-text uno-page__status">
      {{ gameViewLoadError }}
    </p>

    <div v-if="!canShowGameView" class="uno-page__loading-shell">
      <p class="empty-text">正在校验房间状态…</p>
    </div>

    <StrategyTurnMultiplayerLayout v-else>
      <template #topRoomBar>
        <div class="uno-page__play-bar">
          <span class="uno-page__play-room muted-small">{{ playRoomLabel }}</span>
          <button
            type="button"
            class="game-action-btn game-action-btn--ghost game-action-btn--sm"
            @click="onLeaveRoom"
          >
            离开房间
          </button>
        </div>
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
            :is-managed="player.isManaged"
            :is-current-turn="player.isCurrentTurn"
            :finish-rank="player.finishRank"
            :show-countdown="player.isCurrentTurn"
            :countdown-seconds="turnTimeoutSeconds"
            :countdown-expires-at-ms="player.isCurrentTurn ? turnDeadlineAtMs : null"
            low-hand-count-label="UNO"
          />
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
            :is-current-turn="player.isCurrentTurn"
            :finish-rank="player.finishRank"
            :show-countdown="player.isCurrentTurn"
            :countdown-seconds="turnTimeoutSeconds"
            :countdown-expires-at-ms="player.isCurrentTurn ? turnDeadlineAtMs : null"
            low-hand-count-label="UNO"
          />
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
          <div
            class="uno-page__self-countdown"
            :class="{ 'uno-page__self-countdown--hidden': !viewerIsCurrentTurn }"
          >
            <TurnCountdown
              v-if="viewerIsCurrentTurn"
              :seconds="turnTimeoutSeconds"
              :expires-at-ms="turnDeadlineAtMs"
            />
          </div>
          <div class="uno-page__actions">
            <TurnActionBar
              :legal-actions="gameViewLegalActions"
              :play-enabled="playActionEnabled"
              :hint-enabled="hintEnabled"
              :disabled="manualActionDisabled"
              :managed-blocked="viewerManagedActive"
              :busy="gameViewPlaybackBusy"
              :show-countdown="false"
              @action="onTurnBarAction"
            >
              <template #middle>
                <button
                  v-if="!viewerManagedActive"
                  type="button"
                  class="game-action-btn turn-action-bar__btn--manage game-action-btn--md"
                  :disabled="gameViewActionBusy || !canShowGameView"
                  @click="onStartManagedMode"
                >
                  托管
                </button>
                <button
                  v-else
                  type="button"
                  class="game-action-btn turn-action-bar__btn--manage game-action-btn--md"
                  :disabled="gameViewActionBusy || !canShowGameView"
                  @click="onStopManagedMode"
                >
                  取消托管
                </button>
              </template>
            </TurnActionBar>
          </div>
          <div class="uno-page__hand">
            <div class="uno-page__hand-row">
              <SelectableItemHand
                :items="handItems"
                :hand-cards="handCards"
                :selected-ids="selectedCardIds"
                :legal-actions="matcherLegalActions"
                :hint-cursor="hintCursor"
                :disabled="interactionDisabled"
                :busy="gameViewPlaybackBusy"
                @select="onHandSelect"
                @selection-change="onHandSelectionChange"
                @match-change="onMatchChange"
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { StrategyTurnMultiplayerLayout } from '../../game-templates/strategy-turn-multiplayer/index.js';
import {
  SelectableItemHand,
  TurnActionBar,
  TurnCountdown,
  TurnPlayerPanel
} from '../../components/game/index.js';
import { TURN_ACTION_BAR_KEY } from '../../components/game/controls/turnControlEnums.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import * as roomService from '../../services/roomService.js';
import * as strategyTurnGameViewService from '../../services/strategyTurnGameViewService.js';
import { canFetchRemote } from '../../services/remoteGate.js';
import { useRoomStore } from '../../stores/roomStore.js';
import UnoCard from './components/UnoCard.vue';
import UnoColorPicker from './components/UnoColorPicker.vue';
import UnoDiscardArea from './components/UnoDiscardArea.vue';
import UnoSettlementDialog from './components/UnoSettlementDialog.vue';
import { useUnoGameView } from './composables/useUnoGameView.js';
import { useStrategyTurnGameView } from '../../composables/useStrategyTurnGameView.js';
import { isWildHandCard, normalizeHandCard } from './unoGameViewUtils.js';
import {
  buildMatcherLegalActions,
  countWildColorCandidates,
  findPlayActionByChooseColor
} from './unoLegalActionsAdapter.js';
import * as unoService from './unoService.js';
import { applyUnoConfig, UNO_CODE } from './unoConfig.js';
import './unoPage.css';

const route = useRoute();
const router = useRouter();
const platform = usePlatformStore();
const roomStore = useRoomStore();
const { currentRoom } = storeToRefs(roomStore);

const {
  version: gameViewVersion,
  viewerPlayerId: gameViewViewerId,
  currentPlayerId: gameViewCurrentPlayerId,
  publicState: gameViewPublicState,
  privateState: gameViewPrivateState,
  legalActions: gameViewLegalActions,
  playbackBusy: gameViewPlaybackBusy
} = useUnoGameView();

const { isGameOver: gameViewIsGameOver } = useStrategyTurnGameView();

const loading = ref(false);
const loadError = ref('');
const gameViewActionBusy = ref(false);
const gameViewLoadError = ref('');
const selectedCardIds = ref([]);
const colorPickerVisible = ref(false);
const hintCursor = ref(0);
const settlementVisible = ref(false);
const settlementDismissed = ref(false);
/** @type {import('vue').Ref<import('../../services/strategyTurnActionMatcher.js').StrategyTurnActionMatcherResult|null>} */
const matchState = ref(null);
/** @type {(() => void)|null} */
let releaseRoomRealtime = null;
/** @type {(() => void)|null} */
let releaseRoomPresence = null;

const activeRoomId = computed(() => String(route.params.roomId || '').trim());
const activeGameCode = computed(() => String(route.params.gameCode || '').trim() || UNO_CODE);
const onlineBlocked = computed(() => !canFetchRemote());

const currentPlayerId = computed(() => roomService.getCurrentPlayerId());

/**
 * @param {object|null|undefined} room
 * @returns {boolean}
 */
function isUserInRoom(room) {
  const playerId = currentPlayerId.value;
  if (!playerId || !room?.members) {
    return false;
  }
  return room.members.some((item) => {
    const samePlayer = String(item?.playerId || '').trim() === playerId;
    return samePlayer && String(item?.managedMode || '').trim() !== 'shell';
  });
}

const isRoomMember = computed(() => isUserInRoom(currentRoom.value));
const viewerRoomMember = computed(() => {
  const viewerId = gameViewViewerId.value;
  const members = currentRoom.value?.members;
  if (!viewerId || !Array.isArray(members)) {
    return null;
  }
  return (
    members.find((item) => String(item?.playerId || '').trim() === String(viewerId || '').trim()) || null
  );
});
const viewerManagedActive = computed(
  () => String(viewerRoomMember.value?.managedMode || '').trim() === 'active'
);

const canShowGameView = computed(() => {
  if (onlineBlocked.value || loading.value) {
    return false;
  }
  if (!currentRoom.value) {
    return false;
  }
  if (!isRoomMember.value) {
    return false;
  }
  const status = String(currentRoom.value.status || '').trim();
  if (status === 'playing') {
    return true;
  }
  if (gameViewIsGameOver.value && !settlementDismissed.value) {
    return true;
  }
  return false;
});

const playRoomLabel = computed(() => {
  const name = String(currentRoom.value?.roomName || '').trim();
  return name || '对局中';
});

const currentColor = computed(() => String(gameViewPublicState.value?.currentColor || '').trim());

const discardPileRecentCards = computed(() => {
  const list = gameViewPublicState.value?.discardPileRecentCards;
  return Array.isArray(list) ? list : [];
});

const turnTimeoutSeconds = computed(() => {
  const raw = Number(gameViewPublicState.value?.turnTimeoutSeconds);
  return Number.isFinite(raw) && raw > 0 ? raw : 60;
});

const turnDeadlineAtMs = computed(() => {
  const raw = Number(gameViewPublicState.value?.currentTurnDeadlineAt);
  return Number.isFinite(raw) && raw > 0 ? raw : null;
});

const handCards = computed(() => {
  const list = gameViewPrivateState.value?.handCards;
  if (!Array.isArray(list)) {
    return [];
  }
  return list.map((item) => normalizeHandCard(item)).filter((item) => item.cardInstanceId);
});

const handItems = computed(() =>
  handCards.value.map((card) => ({
    id: card.cardInstanceId,
    cardCode: card.cardCode,
    cardType: card.cardType
  }))
);

const viewerIsCurrentTurn = computed(
  () => gameViewViewerId.value === currentPlayerIdInTurn.value
);

const interactionDisabled = computed(
  () =>
    !canShowGameView.value ||
    gameViewActionBusy.value ||
    gameViewPlaybackBusy.value ||
    viewerManagedActive.value ||
    gameViewViewerId.value !== currentPlayerIdInTurn.value
);

const manualActionDisabled = computed(
  () =>
    !canShowGameView.value ||
    gameViewActionBusy.value ||
    gameViewPlaybackBusy.value ||
    gameViewViewerId.value !== currentPlayerIdInTurn.value
);

const settlementRankings = computed(() => {
  const list = gameViewPublicState.value?.rankings;
  return Array.isArray(list) ? list : [];
});

const settlementPlayers = computed(() => {
  const list = gameViewPublicState.value?.players;
  return Array.isArray(list) ? list : [];
});

const matcherLegalActions = computed(() => {
  if (interactionDisabled.value) {
    return { selection: { candidates: [], matchFields: ['cardInstanceId'] } };
  }
  return buildMatcherLegalActions(gameViewLegalActions.value);
});

const determinedAction = computed(() => matchState.value?.determinedAction || null);

const selectedWildColorCandidateCount = computed(() => {
  if (!selectedCardIds.value.length) {
    return 0;
  }
  const instanceId = String(selectedCardIds.value[0] || '').trim();
  const handCard = handCards.value.find((item) => item.cardInstanceId === instanceId);
  if (!handCard || !isWildHandCard(handCard)) {
    return 0;
  }
  return countWildColorCandidates(matchState.value?.activeCandidates, selectedCardIds.value);
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
  return Array.isArray(gameViewLegalActions.value)
    ? gameViewLegalActions.value.some(
        (item) => String(item?.actionType || '').trim() === 'PLAY_CARD'
      )
    : false;
});

const currentPlayerIdInTurn = computed(() =>
  String(gameViewCurrentPlayerId.value || gameViewPublicState.value?.currentPlayerId || '').trim()
);

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
  const nickname = String(matched?.nickname || '').trim();
  return nickname || playerId;
}

const opponentPanels = computed(() => {
  const players = gameViewPublicState.value?.players;
  if (!Array.isArray(players)) {
    return [];
  }
  const viewerId = gameViewViewerId.value;
  return players
    .filter((item) => String(item?.playerId || '').trim() !== viewerId)
    .map((item) => {
      const playerId = String(item.playerId || '').trim();
      const finishRank = Number(item.finishRank);
      return {
        playerId,
        nickname: resolvePlayerNickname(playerId),
        handCount: Number(item.handCount) || 0,
        isAi: Boolean(item.isAi),
        isManaged: Boolean(item.isManaged),
        isCurrentTurn: playerId === currentPlayerIdInTurn.value,
        finishRank: Number.isFinite(finishRank) && finishRank > 0 ? finishRank : null
      };
    });
});

const leftPlayerPanels = computed(() => {
  const list = opponentPanels.value;
  if (list.length <= 1) {
    return list;
  }
  const mid = Math.ceil(list.length / 2);
  return list.slice(0, mid);
});

const rightPlayerPanels = computed(() => {
  const list = opponentPanels.value;
  if (list.length <= 1) {
    return [];
  }
  const mid = Math.ceil(list.length / 2);
  return list.slice(mid);
});

watch(
  () => [gameViewIsGameOver.value, gameViewVersion.value, gameViewPlaybackBusy.value],
  ([isOver, version, playbackBusy]) => {
    if (!isOver || !version || playbackBusy || settlementDismissed.value) {
      return;
    }
    settlementVisible.value = true;
  }
);

watch(gameViewVersion, () => {
  selectedCardIds.value = [];
  colorPickerVisible.value = false;
  hintCursor.value = 0;
  matchState.value = null;
});

/** @type {boolean} */
let suppressHintCursorReset = false;

watch(selectedCardIds, () => {
  if (suppressHintCursorReset) {
    suppressHintCursorReset = false;
    return;
  }
  hintCursor.value = 0;
});

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
      loadError.value = '你尚未加入该房间';
      await backToRoomOrLobby();
      return;
    }
    const status = String(currentRoom.value.status || '').trim();
    if (status !== 'playing') {
      await backToRoomOrLobby();
      return;
    }
    strategyTurnGameViewService.setActiveRoom(roomId);
    const baseVersion = strategyTurnGameViewService.getCurrentGameViewVersion();
    if (!baseVersion) {
      await unoService.loadRoomGameView(roomId);
    }
  } catch (err) {
    loadError.value = err?.message || '加载房间失败';
    await backToRoomOrLobby();
  } finally {
    loading.value = false;
  }
}

async function backToRoomOrLobby() {
  const roomId = activeRoomId.value;
  if (roomId) {
    await router.replace({
      name: 'online-room-waiting',
      params: { gameCode: activeGameCode.value, roomId }
    });
  } else {
    await router.replace({ name: 'online-room-list', params: { gameCode: activeGameCode.value } });
  }
}

function navigateToLobby() {
  roomService.resetRoomGameView();
  router.push({ name: 'online-room-list', params: { gameCode: activeGameCode.value } });
}

async function onSettlementClose() {
  settlementVisible.value = false;
  settlementDismissed.value = true;
  await backToRoomOrLobby();
}

async function onLeaveRoom() {
  const roomId = activeRoomId.value;
  if (!roomId) {
    navigateToLobby();
    return;
  }
  gameViewActionBusy.value = true;
  loadError.value = '';
  try {
    await roomService.leaveRoom(roomId);
    roomService.resetRoomGameView();
    await router.push({ name: 'online-room-list', params: { gameCode: activeGameCode.value } });
  } catch (err) {
    loadError.value = err?.message || '离开房间失败';
  } finally {
    gameViewActionBusy.value = false;
  }
}

async function onStartManagedMode() {
  const roomId = activeRoomId.value;
  if (!roomId || viewerManagedActive.value) {
    return;
  }
  gameViewActionBusy.value = true;
  gameViewLoadError.value = '';
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
  gameViewLoadError.value = '';
  try {
    await roomService.stopManagedMode(roomId);
  } catch (err) {
    gameViewLoadError.value = err?.message || '取消托管失败';
  } finally {
    gameViewActionBusy.value = false;
  }
}

/**
 * @param {import('../../services/strategyTurnActionMatcher.js').StrategyTurnActionMatcherResult|null} result
 */
function onMatchChange(result) {
  matchState.value = result;
}

function onHandSelect(payload) {
  if (interactionDisabled.value) {
    return;
  }
  const id = String(payload?.id || '').trim();
  if (!id) {
    return;
  }
  if (selectedCardIds.value.includes(id)) {
    selectedCardIds.value = selectedCardIds.value.filter((item) => item !== id);
  } else if (matchState.value?.selectableCardIds?.includes(id)) {
    selectedCardIds.value = [...selectedCardIds.value, id];
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

function openWildColorPickerIfNeeded() {
  const instanceId = String(selectedCardIds.value[0] || '').trim();
  if (!instanceId) {
    return false;
  }
  const handCard = handCards.value.find((item) => item.cardInstanceId === instanceId);
  if (!handCard || !isWildHandCard(handCard)) {
    return false;
  }
  const wildColorCount = countWildColorCandidates(
    matchState.value?.activeCandidates,
    selectedCardIds.value
  );
  if (wildColorCount <= 1) {
    return false;
  }
  colorPickerVisible.value = true;
  return true;
}

function onColorPickerCancel() {
  colorPickerVisible.value = false;
}

/**
 * @param {{ color: string }} payload
 */
async function onColorPicked(payload) {
  const chooseColor = String(payload?.color || '').trim();
  colorPickerVisible.value = false;
  if (!chooseColor) {
    return;
  }
  const action = findPlayActionByChooseColor(
    matchState.value?.activeCandidates,
    chooseColor,
    selectedCardIds.value
  );
  const actionId = String(action?.actionId || '').trim();
  if (!actionId) {
    gameViewLoadError.value = '当前无法打出该牌';
    return;
  }
  selectedCardIds.value = [];
  await submitGameAction(actionId);
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
  if (!roomId || interactionDisabled.value) {
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
    await unoService.applyRoomGameAction(roomId, {
      actionId: normalized,
      baseVersion,
      clientSeq: Date.now()
    });
    selectedCardIds.value = [];
    hintCursor.value = 0;
  } catch (err) {
    gameViewLoadError.value = err?.message || '操作失败';
  } finally {
    gameViewActionBusy.value = false;
  }
}

/**
 * @param {{ barKey: string; actionType: string; legalActions: object[] }} payload
 */
async function onTurnBarAction(payload) {
  if (interactionDisabled.value) {
    return;
  }
  if (payload.barKey === TURN_ACTION_BAR_KEY.UI_ACTION_HINT) {
    const suggested = matchState.value?.suggestedSelection;
    if (Array.isArray(suggested) && suggested.length > 0) {
      suppressHintCursorReset = true;
      selectedCardIds.value = [...suggested];
    }
    if (matchState.value?.nextHintCursor != null) {
      hintCursor.value = matchState.value.nextHintCursor;
    }
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

    await submitGameAction(actionId);
    return;
  }

  const actions = Array.isArray(payload.legalActions) ? payload.legalActions : [];
  const action = actions[0];
  const actionId = String(action?.actionId || '').trim();
  if (!actionId) {
    return;
  }
  await submitGameAction(actionId);
}

onMounted(async () => {
  platform.setCurrentGame(activeGameCode.value);
  if (onlineBlocked.value) {
    return;
  }
  try {
    applyUnoConfig();
  } catch {
    // 配置错误在 service 内部处理
  }
  const roomId = activeRoomId.value;
  if (!roomId) {
    await backToRoomOrLobby();
    return;
  }
  if (releaseRoomRealtime) {
    releaseRoomRealtime();
    releaseRoomRealtime = null;
  }
  if (releaseRoomPresence) {
    releaseRoomPresence();
    releaseRoomPresence = null;
  }
  releaseRoomRealtime = roomService.bindRoomRealtime(roomId);
  releaseRoomPresence = roomService.bindRoomPresencePong(
    roomId,
    activeGameCode.value,
    () => String(route.params.roomId || '').trim() === roomId
  );
  await ensureRoomAndGameView();
});

watch(
  () => currentRoom.value?.status,
  (status) => {
    const normalized = String(status || '').trim();
    if (!activeRoomId.value) {
      return;
    }
    if (normalized !== 'playing') {
      if (gameViewIsGameOver.value && !settlementDismissed.value) {
        if (!settlementVisible.value && gameViewVersion.value && !gameViewPlaybackBusy.value) {
          settlementVisible.value = true;
        }
        return;
      }
      roomService.resetRoomGameView();
      void backToRoomOrLobby();
    }
  }
);

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

