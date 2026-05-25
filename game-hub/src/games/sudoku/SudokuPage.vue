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
      :game-code="SUDOKU_CODE"
      :mode="SUDOKU_MODE"
      :difficulty-code="difficultyCode"
      board-title="对局信息"
      board-frame-title="对局区域"
      board-subtitle="点击空格填数 · 可开启草稿模式 · 右键擦除"
      :paused="isPaused"
      @field-change="onControlFieldChange"
      @action="onLayoutAction"
      @resume="resumeGame"
    >
      <template #shop>
        <GameShopPanel :game-code="SUDOKU_CODE" :session-id="matchSessionId" />
      </template>

      <template #ranking>
        <GameRankingPanel
          :game-code="SUDOKU_CODE"
          :mode="SUDOKU_MODE"
          :difficulty-code="difficultyCode"
          value-metric="durationMs"
          :subtitle="`${difficultyLabel} · 全服前十名（按用时排序）`"
        />
      </template>

      <template #match-stats>
        <GameMatchStatsPanel
          :stats="matchStats"
          :quotas="matchQuotas"
          :message="matchStatsMessage"
          theme-seed="sudoku"
        />
      </template>

      <template #board>
        <SudokuBoard
          ref="boardRef"
          :cells="cells"
          :selected-row="selectedRow"
          :selected-col="selectedCol"
          :draft-mode="draftMode"
          :draft-toggle-disabled="!canInteractBoard"
          :interaction-disabled="!canInteractBoard"
          :popup-visible="popupVisible"
          :popup-position="popupPosition"
          :popup-placement="popupPlacement"
          :available-numbers="popupAvailableNumbers"
          @select-cell="onSelectCell"
          @erase-cell="onEraseCell"
          @pick-number="onPickNumber"
          @update:draft-mode="draftMode = $event"
          @close-popup="closePopup"
        />
        <SudokuNumberPanel class="sudoku-board-number-panel" :remaining="remainingCounts" />
      </template>

      <template #inventory>
        <GameInventoryPanel
          :game-code="SUDOKU_CODE"
          :usable-props="[SUDOKU_PROP.HINT]"
          :disabled-props="inventoryDisabledProps"
          :use-labels="inventoryUseLabels"
          @use-prop="useHintProp"
        />
      </template>
    </LightSingleGameLayout>

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
import './styles/sudoku.css';
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import SudokuBoard from './components/SudokuBoard.vue';
import SudokuNumberPanel from './components/SudokuNumberPanel.vue';
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
import {
  computeRemainingCounts,
  countConflictCells,
  countEmptyCells,
  countFilledCells,
  findFirstEmptyEditableCell,
  getAvailableNumbers,
  isCellEditable,
  isPuzzleComplete,
  eraseCell,
  refreshCellConflicts,
  setCellValue,
  toggleDraft
} from './sudokuEngine.js';
import {
  SUDOKU_CODE,
  SUDOKU_MODE,
  SUDOKU_PROP,
  getSudokuModePropLimit,
  getSudokuPropRule,
  getSudokuWinReward
} from './sudokuConfig.js';
import {
  createBoardForDifficulty,
  formatDurationMmSs,
  isFilterUnavailableNumbersEnabled
} from './sudokuService.js';
import { useGamePropQuantities } from '../../composables/useGamePropQuantities.js';
import { useGameSwitchLock } from '../../composables/useGameSwitchLock.js';
import { usePageVisibilityPause } from '../../composables/usePageVisibilityPause.js';
import { createGameSession } from '../../services/gameSessionService.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import {
  getDefaultDifficultyCode,
  getDifficultyName,
  isDifficultyEnabled,
  toDifficultySelectorOptions
} from '../../services/gameDifficultyService.js';
import * as toastService from '../../services/toastService.js';
import { usePlatformStore } from '../../stores/platformStore.js';

const session = createGameSession({ gameCode: SUDOKU_CODE });
const platform = usePlatformStore();
const propQuantities = useGamePropQuantities(SUDOKU_CODE);
const registryGame = getGameConfig(SUDOKU_CODE);
const boardRef = ref(null);

const difficultyOptions = computed(() => toDifficultySelectorOptions(SUDOKU_CODE));
const difficultyCode = ref(getDefaultDifficultyCode(SUDOKU_CODE) || 'easy');

/** @type {import('vue').Ref<import('./sudokuEngine.js').SudokuCell[][]>} */
const cells = ref(createBoardForDifficulty(difficultyCode.value).cells);
const gameStatus = ref('idle');
const elapsedSec = ref(0);
const isPaused = ref(false);
const isSettling = ref(false);
const draftMode = ref(false);
const filterUnavailableNumbers = computed(() => isFilterUnavailableNumbersEnabled());

const selectedRow = ref(-1);
const selectedCol = ref(-1);
const popupVisible = ref(false);
const popupPosition = ref(null);
const popupPlacement = ref('bottom');
const gameMessage = ref('点击空格或填数即可开始对局');
const matchSessionId = ref(null);
const currentMatchPropUses = ref([]);
const usedHintCount = ref(0);
const hintMatchLimit = ref(5);

let timerId = null;

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

/**
 * @param {string} propCode
 * @returns {number}
 */
function propQuantity(propCode) {
  return propQuantities.value[propCode] || 0;
}

/**
 * @param {string} propCode
 * @returns {number}
 */
function propLimit(propCode) {
  const rule = getSudokuPropRule(propCode);
  const fromRule = rule?.maxUsePerMatch != null ? Number(rule.maxUsePerMatch) : null;
  const fromMode = getSudokuModePropLimit(propCode);
  if (Number.isFinite(fromMode)) {
    return fromMode;
  }
  if (Number.isFinite(fromRule)) {
    return fromRule;
  }
  return hintMatchLimit.value;
}

/**
 * @param {string} propCode
 * @returns {number}
 */
function propRemaining(propCode) {
  const limit = propLimit(propCode);
  if (!Number.isFinite(limit)) {
    return 0;
  }
  if (propCode === SUDOKU_PROP.HINT) {
    return Math.max(0, limit - usedHintCount.value);
  }
  return limit;
}

const remainingCounts = computed(() => computeRemainingCounts(cells.value));
const popupAvailableNumbers = computed(() =>
  getAvailableNumbers(
    cells.value,
    selectedRow.value,
    selectedCol.value,
    remainingCounts.value,
    filterUnavailableNumbers.value
  )
);
const canInteractBoard = computed(
  () =>
    (gameStatus.value === 'idle' || gameStatus.value === 'playing') &&
    !isPaused.value &&
    !isSettling.value
);
const canEditBoard = computed(
  () => gameStatus.value === 'playing' && !isPaused.value && !isSettling.value
);
const canRestartGame = computed(() => !isSettling.value);
const canPlayAgain = computed(() => gameStatus.value === 'ended' && !isSettling.value);
const canEndGame = computed(
  () => (gameStatus.value === 'playing' || gameStatus.value === 'settling') && !isSettling.value
);
const canUseHint = computed(
  () =>
    gameStatus.value === 'playing' &&
    !isPaused.value &&
    !isSettling.value &&
    propRemaining(SUDOKU_PROP.HINT) > 0 &&
    propQuantity(SUDOKU_PROP.HINT) > 0
);

const inventoryDisabledProps = computed(() => ({
  [SUDOKU_PROP.HINT]: !canUseHint.value
}));

const inventoryUseLabels = computed(() => ({
  [SUDOKU_PROP.HINT]: '使用'
}));

const difficultyLabel = computed(() => getDifficultyName(SUDOKU_CODE, difficultyCode.value));

const controlFields = computed(() => [
  {
    key: 'difficulty',
    label: '难度',
    type: GAME_CONTROL_TYPE.SELECT,
    value: difficultyCode.value,
    options: difficultyOptions.value,
    disabled:
      gameStatus.value === 'playing' || gameStatus.value === 'settling' || isPaused.value
  }
]);

const matchQuotas = computed(() => [
  {
    label: '提示卡',
    used: propRemaining(SUDOKU_PROP.HINT),
    max: propLimit(SUDOKU_PROP.HINT),
    themeSeed: 'amber'
  }
]);

const matchStats = computed(() => [
  {
    key: 'difficulty',
    label: '难度',
    value: difficultyLabel.value,
    tone: GAME_STAT_TONE.MUTED
  },
  {
    key: 'status',
    label: '对局状态',
    value: statusLabel.value,
    tone: GAME_STAT_TONE.INFO
  },
  {
    key: 'duration',
    label: '用时',
    value: formatDurationMmSs(elapsedSec.value),
    icon: '⏱'
  },
  {
    key: 'filled',
    label: '已填格数',
    value: countFilledCells(cells.value)
  },
  {
    key: 'empty',
    label: '剩余空格',
    value: countEmptyCells(cells.value)
  },
  {
    key: 'hintStock',
    label: '提示卡库存',
    value: propQuantity(SUDOKU_PROP.HINT)
  },
  {
    key: 'hintUsed',
    label: '本局已用提示',
    value: usedHintCount.value
  }
]);

const statusLabel = computed(() => {
  if (isPaused.value && gameStatus.value === 'playing') {
    return '已暂停';
  }
  const map = {
    idle: '未开始',
    playing: '进行中',
    settling: '结算中',
    ended: '已结束'
  };
  return map[gameStatus.value] || '';
});

const matchStatsMessage = computed(() => gameMessage.value);

const layoutGameTitle = computed(() => registryGame?.name || '数独');
const layoutGameSubtitle = computed(() => registryGame?.subName || 'Sudoku');
const layoutGameDescription = computed(() => `经典模式 · ${difficultyLabel.value}`);

const layoutGameStatusText = computed(() => {
  if (isPaused.value && gameStatus.value === 'playing') {
    return '对局已暂停';
  }
  const map = {
    idle: '尚未开始对局',
    playing: '对局进行中',
    settling: '正在结算…',
    ended: '对局已结束'
  };
  return map[gameStatus.value] || '';
});

const actionItems = computed(() => {
  const items = [];
  const status = gameStatus.value;
  const settling = status === 'settling';
  const ended = status === 'ended';
  const playing = status === 'playing';
  const paused = playing && isPaused.value;

  if (ended) {
    items.push({
      key: 'playAgain',
      label: '再来一局',
      type: GAME_ACTION_TYPE.PRIMARY,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: !canPlayAgain.value
    });
    return items;
  }

  if (status === 'idle') {
    return items;
  }

  if (playing && !isPaused.value) {
    items.push({
      key: 'pause',
      label: '暂停游戏',
      type: GAME_ACTION_TYPE.PAUSE,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: settling
    });
  }

  if (paused) {
    items.push({
      key: 'resume',
      label: '继续游戏',
      type: GAME_ACTION_TYPE.RESUME,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: settling
    });
  }

  if (playing || paused || settling) {
    items.push({
      key: 'restart',
      label: '重新开始',
      type: GAME_ACTION_TYPE.SECONDARY,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: !canRestartGame.value
    });
    items.push({
      key: 'end',
      label: '结束对局',
      type: GAME_ACTION_TYPE.DANGER,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: !canEndGame.value
    });
  }

  return items;
});

useGameSwitchLock(
  computed(() => gameStatus.value === 'playing' || gameStatus.value === 'settling')
);

/**
 * @param {string} message
 * @param {string} [level]
 */
function showToast(message, level = 'info') {
  toastService.push(message, level);
}

function stopTimer() {
  if (timerId != null) {
    clearInterval(timerId);
    timerId = null;
  }
}

function startTimer() {
  stopTimer();
  timerId = setInterval(() => {
    if (!isPaused.value && gameStatus.value === 'playing') {
      elapsedSec.value++;
    }
  }, 1000);
}

function ensureSession() {
  if (!matchSessionId.value) {
    matchSessionId.value = session.newMatchSessionId();
  }
}

/**
 * @param {string} [message]
 */
function setupBoard(message) {
  const { cells: nextCells } = createBoardForDifficulty(difficultyCode.value);
  cells.value = nextCells;
  selectedRow.value = -1;
  selectedCol.value = -1;
  closePopup();
  gameMessage.value = message || '点击空格或填数即可开始对局';
}

function resetRuntime(message) {
  stopTimer();
  gameStatus.value = 'idle';
  elapsedSec.value = 0;
  isPaused.value = false;
  isSettling.value = false;
  draftMode.value = false;
  usedHintCount.value = 0;
  matchSessionId.value = null;
  currentMatchPropUses.value = [];
  setupBoard(message);
}

function startMatchIfIdle() {
  if (gameStatus.value !== 'idle') {
    return;
  }
  ensureSession();
  gameStatus.value = 'playing';
  startTimer();
  gameMessage.value = '对局已开始，继续填数完成数独';
}

function pauseGame() {
  if (gameStatus.value !== 'playing' || isPaused.value) {
    return;
  }
  isPaused.value = true;
  closePopup();
  gameMessage.value = '游戏已暂停';
}

function resumeGame() {
  if (!isPaused.value) {
    return;
  }
  isPaused.value = false;
  if (gameStatus.value === 'playing') {
    gameMessage.value = '对局已继续';
  }
}

usePageVisibilityPause({
  shouldPause: () => gameStatus.value === 'playing' && !isPaused.value,
  pause: () => {
    pauseGame();
    if (isPaused.value) {
      gameMessage.value = '页面隐藏，游戏已暂停';
    }
  }
});

function closePopup() {
  popupVisible.value = false;
  popupPosition.value = null;
  popupPlacement.value = 'bottom';
}

/**
 * @param {number} row
 * @param {number} col
 * @returns {string}
 */
function getPopupPlacement(row, col) {
  const rowGroup = Math.floor(row / 3);
  const colGroup = Math.floor(col / 3);
  const placementMap = [
    ['right-bottom', 'right', 'right-top'],
    ['bottom', 'bottom', 'top'],
    ['left-bottom', 'left', 'left-top']
  ];
  return placementMap[colGroup]?.[rowGroup] || 'bottom';
}

/**
 * @param {number} row
 * @param {number} col
 * @param {MouseEvent} event
 */
function openPopupForCell(row, col, event) {
  const exposedBoardRef = boardRef.value?.boardRef;
  const boardEl = exposedBoardRef?.value || exposedBoardRef;
  const cellEl = event?.currentTarget;
  if (!boardEl || !cellEl?.getBoundingClientRect) {
    return;
  }
  const boardRect = boardEl.getBoundingClientRect();
  const cellRect = cellEl.getBoundingClientRect();
  popupPosition.value = {
    left: cellRect.left - boardRect.left + cellRect.width / 2,
    top: cellRect.top - boardRect.top + cellRect.height / 2,
    width: cellRect.width,
    height: cellRect.height,
    boardWidth: boardRect.width,
    boardHeight: boardRect.height,
    row,
    col
  };
  popupPlacement.value = getPopupPlacement(row, col);
  popupVisible.value = true;
}

/**
 * @param {{ row: number; col: number; cell: import('./sudokuEngine.js').SudokuCell; event: MouseEvent }} payload
 */
function onSelectCell(payload) {
  if (!canInteractBoard.value) {
    return;
  }
  const { row, col, cell, event } = payload;
  selectedRow.value = row;
  selectedCol.value = col;
  if (!isCellEditable(cell)) {
    closePopup();
    return;
  }
  openPopupForCell(row, col, event);
}

/**
 * @param {{ row: number; col: number; cell: import('./sudokuEngine.js').SudokuCell; event: MouseEvent }} payload
 */
function onEraseCell(payload) {
  if (!canInteractBoard.value) {
    return;
  }
  const { row, col, cell } = payload;
  if (!isCellEditable(cell) || cell.hinted) {
    return;
  }
  if (!eraseCell(cells.value, row, col)) {
    return;
  }
  selectedRow.value = row;
  selectedCol.value = col;
  closePopup();
  refreshCellConflicts(cells.value);
  if (gameStatus.value === 'playing' && !isPaused.value) {
    afterBoardChange();
    return;
  }
  gameMessage.value = '已擦除';
}

/**
 * @param {number} num
 */
function onPickNumber(num) {
  if (!canInteractBoard.value) {
    return;
  }
  const row = selectedRow.value;
  const col = selectedCol.value;
  if (row < 0 || col < 0) {
    return;
  }
  const cell = cells.value[row][col];
  if (!isCellEditable(cell)) {
    return;
  }
  if (!popupAvailableNumbers.value[num]) {
    return;
  }
  if (gameStatus.value === 'idle') {
    startMatchIfIdle();
  }
  if (!canEditBoard.value) {
    return;
  }
  if (draftMode.value) {
    toggleDraft(cell, num);
    closePopup();
    gameMessage.value = '草稿已更新';
    return;
  }
  setCellValue(cell, num, { hinted: false });
  refreshCellConflicts(cells.value);
  closePopup();
  afterBoardChange();
}

function afterBoardChange() {
  if (isPuzzleComplete(cells.value)) {
    void settleWin();
    return;
  }
  gameMessage.value = '继续填数完成数独';
}

function useHintProp() {
  if (!canUseHint.value) {
    if (gameStatus.value !== 'playing') {
      showToast('对局未进行中', 'warning');
    } else if (isPaused.value) {
      showToast('游戏已暂停', 'warning');
    } else {
      showToast('提示卡不可用', 'warning');
    }
    return;
  }
  let target = null;
  if (selectedRow.value >= 0 && selectedCol.value >= 0) {
    const cell = cells.value[selectedRow.value][selectedCol.value];
    if (isCellEditable(cell) && cell.value == null) {
      target = cell;
    }
  }
  if (!target) {
    const found = findFirstEmptyEditableCell(cells.value);
    target = found?.cell ?? null;
    if (found) {
      selectedRow.value = found.row;
      selectedCol.value = found.col;
    }
  }
  if (!target) {
    showToast('没有可提示的空格', 'warning');
    return;
  }
  setCellValue(target, target.correctValue, { hinted: true });
  refreshCellConflicts(cells.value);
  usedHintCount.value += 1;
  session.trackPropUsage(currentMatchPropUses.value, {
    type: SUDOKU_PROP.HINT,
    propCode: SUDOKU_PROP.HINT,
    label: '提示卡',
    timerSec: elapsedSec.value,
    sessionId: matchSessionId.value
  });
  closePopup();
  gameMessage.value = '已使用提示卡填入正确答案';
  afterBoardChange();
}

async function settleWin() {
  if (gameStatus.value === 'ended' || gameStatus.value === 'settling') {
    return;
  }
  ensureSession();
  isSettling.value = true;
  gameStatus.value = 'settling';
  isPaused.value = false;
  closePopup();
  stopTimer();
  const durationMs = Math.round(elapsedSec.value * 1000);
  const payload = {
    difficultyCode: difficultyCode.value,
    filledCells: countFilledCells(cells.value),
    hintUses: usedHintCount.value,
    errorCount: countConflictCells(cells.value)
  };
  const reward = getSudokuWinReward(elapsedSec.value, difficultyCode.value);
  try {
    await session.settleWin({
      score: durationMs,
      rewardScore: reward,
      difficultyCode: difficultyCode.value,
      durationMs,
      propUses: currentMatchPropUses.value,
      sessionId: matchSessionId.value,
      mode: SUDOKU_MODE,
      matchPayload: payload,
      scorePayload: payload
    });
  } finally {
    isSettling.value = false;
  }
  gameStatus.value = 'ended';
  openResultModal(durationMs, reward);
  gameMessage.value = '恭喜完成数独！';
}

async function settleEnd() {
  if (gameStatus.value === 'ended' || gameStatus.value === 'settling') {
    return;
  }
  ensureSession();
  isSettling.value = true;
  gameStatus.value = 'settling';
  isPaused.value = false;
  closePopup();
  stopTimer();
  const durationMs = Math.round(elapsedSec.value * 1000);
  const filled = countFilledCells(cells.value);
  const endScore = Math.max(0, filled * 2);
  try {
    await session.settleEnd({
      score: endScore,
      difficultyCode: difficultyCode.value,
      durationMs,
      propUses: currentMatchPropUses.value,
      sessionId: matchSessionId.value,
      mode: SUDOKU_MODE,
      payload: { filledCells: filled, hintUses: usedHintCount.value }
    });
  } finally {
    isSettling.value = false;
  }
  gameStatus.value = 'ended';
  openResultModalEnd(durationMs, endScore);
  gameMessage.value = '对局已结束';
}

/**
 * @param {number} durationMs
 * @param {number} reward
 */
function openResultModal(durationMs, reward) {
  Object.assign(resultModal, {
    visible: true,
    title: '本局结算',
    subtitle: '数独完成，成绩已记录',
    resultType: 'success',
    stats: [
      { label: '难度', value: difficultyLabel.value },
      { label: '用时', value: formatDurationMmSs(elapsedSec.value) },
      { label: '提示卡', value: `${usedHintCount.value} 次` },
      { label: '错误格', value: countConflictCells(cells.value) }
    ],
    rewards: [{ label: '平台积分', value: `+${reward}` }],
    highlights: [{ label: '排行榜', value: '按用时升序' }],
    actions: [
      { key: 'restart', label: '再来一局', type: 'primary', disabled: false },
      { key: 'close', label: '关闭', type: 'secondary', disabled: false }
    ]
  });
}

/**
 * @param {number} durationMs
 * @param {number} score
 */
function openResultModalEnd(durationMs, score) {
  Object.assign(resultModal, {
    visible: true,
    title: '本局结算',
    subtitle: '对局已手动结束',
    resultType: 'neutral',
    stats: [
      { label: '难度', value: difficultyLabel.value },
      { label: '用时', value: formatDurationMmSs(elapsedSec.value) },
      { label: '已填格', value: countFilledCells(cells.value) },
      { label: '得分', value: score }
    ],
    rewards: [{ label: '平台积分', value: `+${score}` }],
    highlights: [],
    actions: [
      { key: 'restart', label: '再来一局', type: 'primary', disabled: false },
      { key: 'close', label: '关闭', type: 'secondary', disabled: false }
    ]
  });
}

function restartGame() {
  if (!canRestartGame.value) {
    showToast('请等待结算完成', 'warning');
    return;
  }
  resultModal.visible = false;
  isPaused.value = false;
  matchSessionId.value = session.newMatchSessionId();
  currentMatchPropUses.value = [];
  usedHintCount.value = 0;
  setupBoard('已重新开始');
  gameStatus.value = 'playing';
  elapsedSec.value = 0;
  startTimer();
}

function playAgain() {
  if (!canPlayAgain.value) {
    return;
  }
  resultModal.visible = false;
  resetRuntime('点击空格或填数开始新对局');
}

async function endCurrentGame() {
  if (gameStatus.value === 'idle') {
    showToast('尚未开始对局', 'info');
    return;
  }
  if (gameStatus.value === 'ended' || gameStatus.value === 'settling') {
    return;
  }
  await settleEnd();
}

/**
 * @param {{ key: string; value: unknown }} payload
 */
async function onControlFieldChange(payload) {
  if (payload.key !== 'difficulty') {
    return;
  }
  const next = String(payload.value);
  if (next === difficultyCode.value) {
    return;
  }
  if (gameStatus.value === 'playing' || isPaused.value) {
    showToast('对局进行中，请先结束当前对局', 'warning');
    return;
  }
  if (!isDifficultyEnabled(SUDOKU_CODE, next)) {
    showToast('该难度不可用', 'warning');
    return;
  }
  difficultyCode.value = next;
  resetRuntime('难度已切换，点击空格开始');
  await activateGame(SUDOKU_CODE, {
    difficultyCode: next,
    mode: SUDOKU_MODE,
    includeInventory: true
  });
}

/**
 * @param {string} actionKey
 */
function onLayoutAction(actionKey) {
  if (actionKey === 'playAgain') {
    playAgain();
    return;
  }
  if (actionKey === 'restart') {
    restartGame();
    return;
  }
  if (actionKey === 'pause') {
    pauseGame();
    return;
  }
  if (actionKey === 'resume') {
    resumeGame();
    return;
  }
  if (actionKey === 'end') {
    void endCurrentGame();
  }
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

onMounted(async () => {
  platform.setCurrentGame(SUDOKU_CODE);
  const rule = getSudokuPropRule(SUDOKU_PROP.HINT);
  if (rule?.maxUsePerMatch != null) {
    hintMatchLimit.value = Number(rule.maxUsePerMatch);
  }
  resetRuntime();
  await activateGame(SUDOKU_CODE, {
    mode: SUDOKU_MODE,
    difficultyCode: difficultyCode.value,
    includeInventory: true
  });
});

onBeforeUnmount(() => {
  stopTimer();
});

</script>

<style scoped>
.sudoku-stats-panel {
  margin-top: 12px;
}
</style>
