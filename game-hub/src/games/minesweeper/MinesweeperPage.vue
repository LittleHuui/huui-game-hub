<template>
  <div>
    <LightSingleGameLayout
      :game-title="layoutGameTitle"
      :game-subtitle="layoutGameSubtitle"
      :game-description="layoutGameDescription"
      :game-status-text="layoutGameStatusText"
      :control-fields="controlFields"
      :action-items="actionItems"
      :show-shop="true"
      :show-ranking="true"
      :show-inventory="true"
      :game-code="MINESWEEPER_GAME_CODE"
      :mode="MINESWEEPER_MODE"
      :difficulty-code="difficulty"
      board-title="对局信息"
      board-frame-title="对局区域"
      board-subtitle="左键翻开 · 右键标记"
      :paused="isPaused"
      @field-change="handleControlChange"
      @action="handleControlAction"
      @resume="resumeGame"
    >
      <template #title-extra>
        <div class="info-tip-wrap" tabindex="0">
          <button type="button" class="info-tip-btn" aria-label="积分规则说明">!</button>
          <div class="info-tip-bubble" role="tooltip">
            积分规则：胜利直接获得当前难度满积分（初级100 / 中级300 / 高级800）；失败或主动结束时，按正确标记雷数 × 3 结算。
          </div>
        </div>
      </template>

      <template #shop>
        <GameShopPanel :game-code="MINESWEEPER_GAME_CODE" :session-id="matchSessionId" />
      </template>

      <template #ranking>
        <GameRankingPanel
          :game-code="MINESWEEPER_GAME_CODE"
          :mode="MINESWEEPER_MODE"
          :difficulty-code="difficulty"
          value-metric="durationMs"
          :subtitle="`${difficultyLabel} · 全服前十名（按用时排序）`"
        />
      </template>

      <template #match-stats>
        <GameMatchStatsPanel
          :stats="matchStats"
          :quotas="matchQuotas"
          :message="gameMessage"
          :theme-seed="statThemeSeed"
        />
      </template>

      <template #board>
        <MinesweeperBattlePanel
          :board="board"
          :rows="rows"
          :cols="cols"
          :window-width="windowWidth"
          :neighbor-ring-keys="neighborRingKeys"
          :board-shake="boardShake"
          :game-win="gameWin"
          @cell-click="clickCell"
          @cell-right="rightClick"
          @ring-enter="onNeighborRingCellEnter"
          @ring-leave="onNeighborRingCellLeave"
          @clear-ring="clearNeighborRing"
        />
      </template>

      <template #inventory>
        <GameInventoryPanel
          :game-code="MINESWEEPER_GAME_CODE"
          :usable-props="[MINESWEEPER_PROP.HINT]"
          :active-prop="activeTool === 'hint' ? MINESWEEPER_PROP.HINT : ''"
          :disabled-props="inventoryDisabledProps"
          :use-labels="inventoryUseLabels"
          @use-prop="onInventoryUseProp"
        >
          <template #item-extra="{ item }">
            <button
              v-if="item.propCode === MINESWEEPER_PROP.REVIVE"
              type="button"
              class="game-inventory-use minesweeper-auto-revive-btn"
              :class="{ 'minesweeper-auto-revive-btn--active': user.autoRevive }"
              :disabled="reviveQty <= 0"
              title="有卡且本局未复活时，踩雷自动消耗一张"
              @click="setAutoRevive(!user.autoRevive)"
            >
              用
            </button>
          </template>
        </GameInventoryPanel>
      </template>
    </LightSingleGameLayout>

    <MinesweeperReviveModal
      :visible="reviveOffer.visible"
      :seconds-left="reviveOffer.secondsLeft"
      :revive-disabled="reviveQty <= 0"
      @confirm="confirmReviveOffer"
      @decline="declineReviveOffer"
    />

    <GameResultModal
      :visible="resultModal.visible"
      :title="resultModal.title"
      :subtitle="resultModal.subtitle"
      :result-type="resultModal.resultType"
      :stats="resultModal.stats"
      :rewards="resultModal.rewards"
      :highlights="resultModal.highlights"
      :actions="resultModal.actions"
      @action="onResultModalAction"
      @close="resultModal.visible = false"
    />
  </div>
</template>

<script setup>
import './minesweeper.css';
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import MinesweeperReviveModal from './components/MinesweeperReviveModal.vue';
import MinesweeperBattlePanel from './components/MinesweeperBattlePanel.vue';
import { LightSingleGameLayout } from '../../game-templates/light-single/index.js';
import {
  GameMatchStatsPanel,
  GameResultModal,
  GameShopPanel,
  GameRankingPanel,
  GameInventoryPanel,
  GAME_ACTION_SIZE,
  GAME_ACTION_TYPE,
  GAME_CONTROL_TYPE,
  GAME_STAT_TONE
} from '../../components/game/index.js';
import { getGameConfig } from '../../constants/gameRegistry.js';
import * as Svc from './minesweeperService.js';
import {
  MINESWEEPER_GAME_CODE,
  MINESWEEPER_MODE,
  MINESWEEPER_PRESETS,
  MINESWEEPER_PROP,
  HINT_LIMIT_BY_DIFFICULTY
} from './minesweeperConfig.js';
import { useGamePropQuantities } from '../../composables/useGamePropQuantities.js';
import { createGameSession } from '../../services/gameSessionService.js';
import {
  getDefaultDifficultyCode,
  getDifficultyName,
  isDifficultyEnabled,
  toDifficultySelectorOptions
} from '../../services/gameDifficultyService.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import * as toastService from '../../services/toastService.js';
import { useGameSwitchLock } from '../../composables/useGameSwitchLock.js';
import { usePageVisibilityPause } from '../../composables/usePageVisibilityPause.js';
import { usePlatformStore } from '../../stores/platformStore.js';

/** 统计区配色：0–9 | 主题名 | random */
const statThemeSeed = 'random';
const session = createGameSession({ gameCode: MINESWEEPER_GAME_CODE });
const platform = usePlatformStore();
const user = session.currentUser;
const propQuantities = useGamePropQuantities(MINESWEEPER_GAME_CODE);
const registryGame = getGameConfig(MINESWEEPER_GAME_CODE);

/**
 * @param {string} propCode
 * @returns {number}
 */
function propQty(propCode) {
  return propQuantities.value[propCode] || 0;
}

const hintQty = computed(() => propQty(MINESWEEPER_PROP.HINT));
const reviveQty = computed(() => propQty(MINESWEEPER_PROP.REVIVE));
const difficultyOptions = computed(() => toDifficultySelectorOptions(MINESWEEPER_GAME_CODE));
const difficulty = ref(getDefaultDifficultyCode(MINESWEEPER_GAME_CODE) || 'easy');

/** 首帧渲染早于 onMounted，必须与 rows/cols 同步为完整棋盘，避免 flattenBoard 读 undefined */
const initialPreset = MINESWEEPER_PRESETS[difficulty.value];
const rows = ref(initialPreset.rows);
const cols = ref(initialPreset.cols);
const mines = ref(initialPreset.mines);
const board = ref(Svc.createEmptyBoard(initialPreset.rows, initialPreset.cols));
Svc.initBoard(board.value, initialPreset.rows, initialPreset.cols, initialPreset.mines);
const timer = ref(0);
let timerInstance = null;
const gameStarted = ref(false);
const gameOver = ref(false);
const gameWin = ref(false);
const boardShake = ref(false);
const gameMessage = ref('开始你的扫雷挑战吧');
const activeTool = ref('');
const isPaused = ref(false);
const safeHintUsed = ref(false);
const usedHintCount = ref(0);
const revived = ref(false);
const matchSessionId = ref(null);
const currentMatchPropUses = ref([]);
const reviveOffer = reactive({
  visible: false,
  cell: null,
  secondsLeft: 5,
  tickTimerId: null
});
const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1200);
const neighborRingKeys = ref({});
const resultModal = reactive({
  visible: false,
  title: '本局结算',
  subtitle: '',
  resultType: 'neutral',
  stats: [],
  rewards: [],
  highlights: [],
  actions: []
});

const isGameInProgress = computed(() => gameStarted.value && !gameOver.value);

useGameSwitchLock(isGameInProgress);
const flatBoard = computed(() => Svc.flattenBoard(board.value, rows.value, cols.value));
const neighborHoverRingEnabled = computed(() => user.value.prefs?.neighborHoverRing !== false);
const remainMines = computed(() => {
  let flagCount = 0;
  for (const v of flatBoard.value) {
    if (v && v.flagged) {
      flagCount++;
    }
  }
  return mines.value - flagCount;
});
const openedCount = computed(() => Svc.countOpened(board.value, rows.value, cols.value));
const flaggedCount = computed(() => {
  let count = 0;
  for (const cell of flatBoard.value) {
    if (cell?.flagged) {
      count++;
    }
  }
  return count;
});
const canUseBattleProps = computed(() => isGameInProgress.value && !isPaused.value && !reviveOffer.visible);
const hintMatchLimit = computed(() => HINT_LIMIT_BY_DIFFICULTY[difficulty.value] ?? 2);
const hintMatchRemaining = computed(() => {
  const matchQuota = Math.max(0, hintMatchLimit.value - usedHintCount.value);
  return Math.min(hintQty.value, matchQuota);
});
const reviveMatchLimit = 1;
const reviveMatchRemaining = computed(() => {
  if (revived.value) {
    return 0;
  }
  return Math.min(reviveQty.value, reviveMatchLimit);
});
const hintBackpackExhausted = computed(
  () => hintQty.value <= 0 || usedHintCount.value >= hintMatchLimit.value
);
const canUseSafeStartHint = computed(() => !isGameInProgress.value);
const difficultyLabel = computed(() => getDifficultyName(MINESWEEPER_GAME_CODE, difficulty.value));

const layoutGameTitle = computed(() => registryGame?.name || '雷区突围');
const layoutGameSubtitle = computed(() => registryGame?.subName || 'Mine Rush');
const layoutGameDescription = computed(() => `单人模式 · ${difficultyLabel.value}`);

const layoutGameStatusText = computed(() => {
  if (gameOver.value) {
    return '对局已结束';
  }
  if (isGameInProgress.value && isPaused.value) {
    return '对局已暂停';
  }
  if (isGameInProgress.value) {
    return '对局进行中';
  }
  return '尚未开始对局';
});

const controlFields = computed(() => [
  {
    key: 'difficulty',
    label: '难度',
    type: GAME_CONTROL_TYPE.SELECT,
    value: difficulty.value,
    options: difficultyOptions.value,
    disabled: isGameInProgress.value
  }
]);

const actionItems = computed(() => {
  const items = [];
  const inProgress = isGameInProgress.value;
  const ended = gameOver.value;
  const paused = inProgress && isPaused.value;

  if (ended) {
    items.push({
      key: 'playAgain',
      label: '再来一局',
      type: GAME_ACTION_TYPE.PRIMARY,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: false
    });
    if (canUseSafeStartHint.value) {
      items.push({
        key: 'safeStart',
        label: '安全开局',
        type: GAME_ACTION_TYPE.SUCCESS,
        size: GAME_ACTION_SIZE.MD,
        visible: true,
        disabled: false
      });
    }
    return items;
  }

  if (inProgress && !isPaused.value) {
    items.push({
      key: 'pause',
      label: '暂停游戏',
      type: GAME_ACTION_TYPE.PAUSE,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: false
    });
  }

  if (paused) {
    items.push({
      key: 'resume',
      label: '继续游戏',
      type: GAME_ACTION_TYPE.RESUME,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: false
    });
  }

  if (inProgress) {
    items.push({
      key: 'restart',
      label: '重新开始',
      type: GAME_ACTION_TYPE.SECONDARY,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: false
    });
    items.push({
      key: 'end',
      label: '结束对局',
      type: GAME_ACTION_TYPE.DANGER,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: false
    });
  }

  if (canUseSafeStartHint.value) {
    items.push({
      key: 'safeStart',
      label: '安全开局',
      type: GAME_ACTION_TYPE.SUCCESS,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: false
    });
  }

  return items;
});

const matchQuotas = computed(() => [
  {
    label: '提示可用',
    used: hintMatchRemaining.value,
    max: hintMatchLimit.value,
    themeSeed: 'amber'
  },
  {
    label: '复活可用',
    used: reviveMatchRemaining.value,
    max: reviveMatchLimit,
    themeSeed: 'cyan'
  }
]);

const matchStats = computed(() => [
  {
    key: 'score',
    label: '当前积分',
    value: user.value.score || 0,
    tone: GAME_STAT_TONE.ACCENT,
    icon: '★'
  },
  {
    key: 'remainMines',
    label: '剩余雷',
    value: remainMines.value,
    icon: '💣'
  },
  {
    key: 'duration',
    label: '用时',
    value: `${timer.value}s`,
    icon: '⏱'
  },
  {
    key: 'opened',
    label: '已翻开',
    value: openedCount.value,
    icon: '▣'
  },
  {
    key: 'flagged',
    label: '已标记',
    value: flaggedCount.value,
    icon: '⚑'
  },
  {
    key: 'difficulty',
    label: '难度',
    value: difficultyLabel.value,
    tone: GAME_STAT_TONE.MUTED
  }
]);

const inventoryDisabledProps = computed(() => ({
  [MINESWEEPER_PROP.HINT]: !canUseBattleProps.value || hintBackpackExhausted.value
}));

const inventoryUseLabels = computed(() => ({
  [MINESWEEPER_PROP.HINT]: activeTool.value === 'hint' ? '选格' : '用'
}));

/**
 * 左侧配置项变更。
 * @param {{ key: string; value: unknown }} payload
 */
function handleControlChange(payload) {
  if (payload.key === 'difficulty') {
    changeDifficulty(payload.value);
  }
}

/**
 * 轻量单人模板操作按钮回调。
 * @param {string} actionKey
 */
function handleControlAction(actionKey) {
  if (actionKey === 'pause') {
    pauseGame();
    return;
  }
  if (actionKey === 'resume') {
    resumeGame();
    return;
  }
  if (actionKey === 'restart') {
    restartGame();
    return;
  }
  if (actionKey === 'playAgain') {
    playAgain();
    return;
  }
  if (actionKey === 'safeStart') {
    safeStartHint();
    return;
  }
  if (actionKey === 'end') {
    endCurrentGame();
  }
}

/**
 * 背包道具使用。
 * @param {string} propCode
 */
function onInventoryUseProp(propCode) {
  if (propCode === MINESWEEPER_PROP.HINT) {
    useHintCard();
  }
}

function showToast(message, level = 'info', duration = 3200, toastKind = null) {
  toastService.push(message, level, duration, toastKind);
}

watch(
  () => user.value.prefs?.neighborHoverRing,
  (enabled) => {
    if (enabled === false) {
      clearNeighborRing();
    }
  }
);

function ensureSession() {
  if (!matchSessionId.value) {
    matchSessionId.value = session.newMatchSessionId();
    currentMatchPropUses.value = [];
  }
}

function stopReviveOfferTimer() {
  if (reviveOffer.tickTimerId) {
    clearInterval(reviveOffer.tickTimerId);
    reviveOffer.tickTimerId = null;
  }
}

function recordPropUsage(propCode, label) {
  ensureSession();
  session.trackPropUsage(currentMatchPropUses.value, {
    propCode,
    label,
    timerSec: timer.value,
    sessionId: matchSessionId.value
  });
}

function clearNeighborRing() {
  neighborRingKeys.value = {};
}

function applyNeighborRingKeysFromCenter(center) {
  const next = {};
  for (let dr = -1; dr <= 1; dr++) {
    for (let dc = -1; dc <= 1; dc++) {
      if (dr === 0 && dc === 0) {
        continue;
      }
      const r = center.row + dr;
      const c = center.col + dc;
      if (r >= 0 && r < rows.value && c >= 0 && c < cols.value) {
        next[`${r}-${c}`] = true;
      }
    }
  }
  neighborRingKeys.value = next;
}

function onNeighborRingCellEnter(cell) {
  if (!neighborHoverRingEnabled.value) {
    neighborRingKeys.value = {};
    return;
  }
  if (cell.opened && !cell.isMine && cell.mineCount > 0) {
    applyNeighborRingKeysFromCenter(cell);
  } else {
    neighborRingKeys.value = {};
  }
}

function onNeighborRingCellLeave() {
  clearNeighborRing();
}

function startTimer() {
  stopTimer();
  timerInstance = setInterval(() => {
    if (!isPaused.value && isGameInProgress.value) {
      timer.value++;
    }
  }, 1000);
}

function stopTimer() {
  if (timerInstance) {
    clearInterval(timerInstance);
    timerInstance = null;
  }
}

function resetMatchRuntimeState(message) {
  stopTimer();
  clearNeighborRing();
  stopReviveOfferTimer();
  reviveOffer.visible = false;
  reviveOffer.cell = null;
  reviveOffer.secondsLeft = 5;
  matchSessionId.value = null;
  currentMatchPropUses.value = [];
  timer.value = 0;
  gameStarted.value = false;
  gameOver.value = false;
  gameWin.value = false;
  boardShake.value = false;
  usedHintCount.value = 0;
  revived.value = false;
  activeTool.value = '';
  isPaused.value = false;
  safeHintUsed.value = false;
  gameMessage.value = message || '游戏开始';
}

function startGame(message) {
  resetMatchRuntimeState(message);
  const preset = MINESWEEPER_PRESETS[difficulty.value];
  const nextRows = preset.rows;
  const nextCols = preset.cols;
  const nextMines = preset.mines;
  const nextBoard = Svc.createEmptyBoard(nextRows, nextCols);
  Svc.initBoard(nextBoard, nextRows, nextCols, nextMines);
  /** 先换 board 再换 rows/cols，避免中间帧出现「新尺寸 + 旧棋盘」导致 flattenBoard 读 undefined */
  board.value = nextBoard;
  rows.value = nextRows;
  cols.value = nextCols;
  mines.value = nextMines;
}

function restartGame() {
  startGame();
  ensureSession();
  gameStarted.value = true;
  startTimer();
  gameMessage.value = '已重新开始，翻格继续';
}

/**
 * 已结束对局：再来一局（重置棋盘，首次翻格自动开局）。
 */
function playAgain() {
  resultModal.visible = false;
  startGame('翻格即可开始新对局');
}

/**
 * 切换难度（对局未进行中）。
 * @param {string} value
 */
function changeDifficulty(value) {
  if (isGameInProgress.value) {
    showToast('对局进行中，无法切换难度', 'warning');
    return;
  }
  if (!isDifficultyEnabled(MINESWEEPER_GAME_CODE, value)) {
    showToast('该难度不可用', 'warning');
    return;
  }
  difficulty.value = value;
  startGame();
}

/**
 * 暂停对局：停止计时并锁定棋盘操作。
 */
function pauseGame() {
  if (gameOver.value || isPaused.value) {
    return;
  }
  isPaused.value = true;
  gameMessage.value = '游戏已暂停';
}

/**
 * 恢复对局。
 */
function resumeGame() {
  if (!isPaused.value) {
    return;
  }
  isPaused.value = false;
  if (gameStarted.value && !gameOver.value) {
    gameMessage.value = '游戏继续';
  }
}

usePageVisibilityPause({
  shouldPause: () => isGameInProgress.value && !isPaused.value,
  pause: () => {
    pauseGame();
    if (isPaused.value) {
      gameMessage.value = '已离开当前页面，游戏已自动暂停。返回后请点击「继续游戏」。';
    }
  }
});

function rightClick(cell) {
  if (gameOver.value || isPaused.value || reviveOffer.visible) {
    return;
  }
  if (cell.opened) {
    return;
  }
  if (!cell.flagged && !cell.question) {
    cell.flagged = true;
    return;
  }
  if (cell.flagged) {
    cell.flagged = false;
    cell.question = true;
    return;
  }
  if (cell.question) {
    cell.question = false;
  }
}

function clickCell(cell) {
  if (gameOver.value || isPaused.value || reviveOffer.visible) {
    return;
  }
  if (!gameStarted.value) {
    ensureSession();
    gameStarted.value = true;
    startTimer();
  }
  if (activeTool.value === 'hint') {
    handleHint(cell);
    return;
  }
  if (cell.flagged || cell.opened) {
    return;
  }
  if (cell.isMine) {
    if (revived.value) {
      failGame();
      return;
    }
    if (reviveQty.value > 0) {
      if (user.value.autoRevive) {
        applyReviveFromMine(cell);
        return;
      }
      startReviveOffer(cell);
      return;
    }
    failGame();
    return;
  }
  Svc.openCell(cell, board.value, rows.value, cols.value);
  if (Svc.isWinState(board.value, rows.value, cols.value, mines.value)) {
    winGame();
  }
}

function safeStartHint() {
  if (!canUseSafeStartHint.value) {
    return;
  }
  if (gameOver.value || safeHintUsed.value) {
    startGame();
  }
  const flat = flatBoard.value.filter((v) => v && !v.isMine && !v.opened);
  if (flat.length === 0) {
    return;
  }
  const randomCell = flat[Math.floor(Math.random() * flat.length)];
  randomCell.opened = true;
  if (randomCell.mineCount === 0) {
    Svc.expandZero(board.value, rows.value, cols.value, randomCell.row, randomCell.col);
  }
  safeHintUsed.value = true;
  ensureSession();
  gameStarted.value = true;
  startTimer();
  gameMessage.value = '已安全开局，计时开始';
  if (Svc.isWinState(board.value, rows.value, cols.value, mines.value)) {
    winGame();
  }
}

/**
 * @param {'win'|'fail'|'end'} kind
 * @param {number} rewardScore
 */
function openResultModal(kind, rewardScore) {
  const resultLabel = kind === 'win' ? '胜利' : kind === 'fail' ? '失败' : '已结束';
  const resultType = kind === 'win' ? 'success' : kind === 'fail' ? 'failed' : 'neutral';
  const subtitle =
    kind === 'win'
      ? '恭喜通关，本局成绩已记录'
      : kind === 'fail'
        ? '踩雷失败，本局成绩已记录'
        : '对局已手动结束';
  Object.assign(resultModal, {
    visible: true,
    title: '本局结算',
    subtitle,
    resultType,
    stats: [
      { label: '结果', value: resultLabel },
      { label: '难度', value: difficultyLabel.value },
      { label: '用时', value: formatDurationMmSs(timer.value) },
      { label: '剩余地雷数', value: remainMines.value },
      { label: '翻开格子数', value: openedCount.value },
      { label: '标记数', value: flaggedCount.value }
    ],
    rewards: [{ label: '平台积分', value: `+${rewardScore}` }],
    highlights: [{ label: '是否进入排行榜', value: kind === 'win' ? '是' : '否' }],
    actions: [
      { key: 'restart', label: '再来一局', type: 'primary', disabled: false },
      { key: 'close', label: '关闭', type: 'secondary', disabled: false }
    ]
  });
}

/**
 * @param {string} actionKey
 */
function onResultModalAction(actionKey) {
  if (actionKey === 'restart') {
    resultModal.visible = false;
    playAgain();
    return;
  }
  if (actionKey === 'close') {
    resultModal.visible = false;
  }
}

/**
 * @param {number} totalSec
 * @returns {string}
 */
function formatDurationMmSs(totalSec) {
  const sec = Math.max(0, Math.floor(totalSec));
  const minutes = Math.floor(sec / 60);
  const seconds = sec % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

async function endCurrentGame() {
  if (!isGameInProgress.value) {
    return;
  }
  isPaused.value = false;
  stopTimer();
  gameOver.value = true;
  const correctFlags = Svc.countCorrectFlags(board.value, rows.value, cols.value);
  const endScore = correctFlags * 3;
  await session.settleEnd({
    score: endScore,
    difficultyCode: difficulty.value,
    durationMs: Math.round(timer.value * 1000),
    mode: MINESWEEPER_MODE,
    propUses: currentMatchPropUses.value,
    sessionId: matchSessionId.value
  });
  openResultModal('end', endScore);
  gameMessage.value = `已结束对局，获得 ${endScore} 积分`;
}

async function failGame() {
  stopReviveOfferTimer();
  reviveOffer.visible = false;
  reviveOffer.cell = null;
  gameOver.value = true;
  stopTimer();
  boardShake.value = true;
  const correctFlags = Svc.countCorrectFlags(board.value, rows.value, cols.value);
  const failScore = correctFlags * 3;
  await session.settleFail({
    score: failScore,
    difficultyCode: difficulty.value,
    durationMs: Math.round(timer.value * 1000),
    mode: MINESWEEPER_MODE,
    propUses: currentMatchPropUses.value,
    sessionId: matchSessionId.value
  });
  flatBoard.value.forEach((v) => {
    if (v && v.isMine) {
      v.opened = true;
    }
  });
  setTimeout(() => {
    boardShake.value = false;
  }, 500);
  openResultModal('fail', failScore);
  gameMessage.value = `游戏失败，获得 ${failScore} 积分`;
}

async function winGame() {
  gameOver.value = true;
  gameWin.value = true;
  stopTimer();
  const score = MINESWEEPER_PRESETS[difficulty.value].scoreWin;
  await session.settleWin({
    score,
    difficultyCode: difficulty.value,
    durationMs: Math.round(timer.value * 1000),
    mode: MINESWEEPER_MODE,
    propUses: currentMatchPropUses.value,
    sessionId: matchSessionId.value
  });
  openResultModal('win', score);
  gameMessage.value = `胜利！获得 ${score} 积分`;
  showToast('恭喜胜利', 'success');
}

function startReviveOffer(cell) {
  stopReviveOfferTimer();
  reviveOffer.visible = true;
  reviveOffer.cell = cell;
  reviveOffer.secondsLeft = 5;
  reviveOffer.tickTimerId = setInterval(() => {
    reviveOffer.secondsLeft--;
    if (reviveOffer.secondsLeft <= 0) {
      declineReviveOffer();
    }
  }, 1000);
}

async function confirmReviveOffer() {
  if (!reviveOffer.visible || !reviveOffer.cell) {
    return;
  }
  if (reviveQty.value <= 0) {
    showToast('没有可用的复活卡', 'warning');
    return;
  }
  const cell = reviveOffer.cell;
  stopReviveOfferTimer();
  reviveOffer.visible = false;
  reviveOffer.cell = null;
  await applyReviveFromMine(cell);
}

async function declineReviveOffer() {
  if (!reviveOffer.visible) {
    return;
  }
  stopReviveOfferTimer();
  reviveOffer.visible = false;
  reviveOffer.cell = null;
  if (gameOver.value) {
    return;
  }
  failGame();
}

async function applyReviveFromMine(cell) {
  revived.value = true;
  recordPropUsage(MINESWEEPER_PROP.REVIVE, '复活卡：踩中格已标雷旗');
  cell.flagged = true;
  gameMessage.value = '复活卡已触发';
  showToast('已使用复活卡', 'success');
  session.persistLocal();
}

function useHintCard() {
  if (!canUseBattleProps.value) {
    showToast('对局未开始、已结束或已暂停时不可使用道具', 'warning');
    return;
  }
  if (hintQty.value <= 0) {
    showToast('没有提示卡', 'warning');
    return;
  }
  if (usedHintCount.value >= hintMatchLimit.value) {
    showToast('本局提示次数已达上限', 'warning');
    return;
  }
  activeTool.value = 'hint';
  gameMessage.value = '请选择一个格子进行提示';
}

async function handleHint(cell) {
  if (cell.opened) {
    return;
  }
  usedHintCount.value++;
  activeTool.value = '';
  const isMine = cell.isMine;
  recordPropUsage(MINESWEEPER_PROP.HINT, isMine ? '提示卡：目标为雷' : '提示卡：目标安全');
  if (isMine) {
    showToast('快看！是大雷！', 'error', 4200, 'hint-mine');
  } else {
    showToast('此处安全', 'success', 4200, 'hint-safe');
  }
  gameMessage.value = '提示已使用';
  session.persistLocal();
}

async function setAutoRevive(value) {
  await session.setAutoRevive(value);
  showToast(value ? '已开启踩雷自动复活' : '已关闭踩雷自动复活', 'info');
}

defineExpose({ clearNeighborRing });

function handleResize() {
  windowWidth.value = window.innerWidth;
}

onMounted(async () => {
  platform.setCurrentGame(MINESWEEPER_GAME_CODE);
  await activateGame(MINESWEEPER_GAME_CODE, {
    mode: MINESWEEPER_MODE,
    difficultyCode: difficulty.value,
    includeInventory: true
  });
  startGame('开始你的扫雷挑战吧');
  window.addEventListener('resize', handleResize);
  handleResize();
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  stopTimer();
  stopReviveOfferTimer();
});
</script>
