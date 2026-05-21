<template>
  <div>
    <GamePlayLayout>
      <template #config>
        <GameConfigPanel :title="configPanelTitle">
          <Match3Hud
            section="config"
            :mode="mode"
            :score="score"
            :moves="moves"
            :combo-max="comboMax"
            :remaining-sec="remainingSec"
            :elapsed-sec="elapsedSec"
            :game-status="gameStatus"
            :locked="isGameInProgress"
            :restart-disabled="!canRestartGame"
            message=""
            :prop-quotas="propQuotas"
            :theme-seed="statThemeSeed"
            @change-mode="changeMode"
            @restart="restartGame"
            @end="endCurrentGame"
          />
        </GameConfigPanel>
      </template>

      <template #shop>
        <GameShopPanel :game-code="MATCH3" :session-id="matchSessionId" />
      </template>

      <template #ranking>
        <GameRankingPanel
          :game-code="MATCH3"
          :mode="mode"
          :difficulty-code="difficultyCode"
          value-metric="score"
          :subtitle="rankingSubtitle"
        />
      </template>

      <template #hud>
        <GameHudPanel>
          <Match3Hud
            section="hud"
            :mode="mode"
            :score="score"
            :moves="moves"
            :combo-max="comboMax"
            :remaining-sec="remainingSec"
            :elapsed-sec="elapsedSec"
            :game-status="gameStatus"
            :locked="isGameInProgress"
            :message="gameMessage"
            :prop-quotas="propQuotas"
            :theme-seed="statThemeSeed"
          />
        </GameHudPanel>
      </template>

      <template #board>
        <div v-if="chainHint" class="match3-chain-hint">{{ chainHint }}</div>
        <Match3Board
          :board="board"
          :items="gameConfig.items || []"
          :active-tool="activeTool"
          :cell-visuals="cellVisuals"
          :cell-size="clientConfig.cellSize || 44"
          :input-locked="inputLocked"
          :swap-ms="animationConfig.swapMs"
          :remove-ms="animationConfig.removeMs"
          :drop-ms="animationConfig.dropMs"
          @swap-request="handleSwapRequest"
          @cell-click="handleBombCellClick"
        />
      </template>

      <template #inventory>
        <GameInventoryPanel
          :game-code="MATCH3"
          :usable-props="[MATCH3_PROP.SHUFFLE, MATCH3_PROP.BOMB]"
          :active-prop="activeTool === 'bomb' ? MATCH3_PROP.BOMB : ''"
          :disabled-props="inventoryDisabledProps"
          :use-labels="inventoryUseLabels"
          @use-prop="useProp"
        />
      </template>
    </GamePlayLayout>

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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import Match3Board from './components/Match3Board.vue';
import Match3Hud from './components/Match3Hud.vue';
import GameResultModal from '../../components/game/GameResultModal.vue';
import GamePlayLayout from '../../components/game/GamePlayLayout.vue';
import GameConfigPanel from '../../components/game/GameConfigPanel.vue';
import GameShopPanel from '../../components/game/GameShopPanel.vue';
import GameRankingPanel from '../../components/game/GameRankingPanel.vue';
import GameHudPanel from '../../components/game/GameHudPanel.vue';
import GameInventoryPanel from '../../components/game/GameInventoryPanel.vue';
import {
  applyBomb,
  canSwap,
  cloneBoard,
  collapseBoard,
  createBoard,
  fillBoardControlled,
  findMatches,
  hasAvailableMove,
  removeMatches,
  scoreMatches,
  shuffleBoard,
  swapCells
} from './match3Engine.js';
import {
  getMatch3ClientConfig,
  getMatch3DifficultyConfig,
  getMatch3ModePropLimit,
  getMatch3PropRule,
  MATCH3_PROP
} from './match3Config.js';
import { useGamePropQuantities } from '../../composables/useGamePropQuantities.js';
import { useGameSwitchLock } from '../../composables/useGameSwitchLock.js';
import { createGameSession } from '../../services/gameSessionService.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import * as toastService from '../../services/toastService.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import {
  getDefaultDifficultyCode,
  getDifficultyName
} from '../../services/gameDifficultyService.js';

const MATCH3 = 'match3';
/** 统计区配色：0–9 | 主题名 | random */
const statThemeSeed = 'random';
const difficultyCode = computed(
  () => getMatch3DifficultyConfig().difficultyCode || getDefaultDifficultyCode(MATCH3)
);
const configPanelTitle = '游戏信息';
const CELL_GAP = 6;
const session = createGameSession({ gameCode: MATCH3 });
const platform = usePlatformStore();
const propQuantities = useGamePropQuantities(MATCH3);

const mode = ref('timed');
const board = ref([]);
const activeTool = ref('');
const cellVisuals = ref({});
const chainHint = ref('');
/** @type {import('vue').Ref<'idle'|'playing'|'paused'|'ended'>} */
const gameStatus = ref('idle');
const score = ref(0);
const moves = ref(0);
const comboMax = ref(0);
const elapsedSec = ref(0);
const remainingSec = ref(180);
const gameMessage = ref('拖动方块交换即可开始');
const matchSessionId = ref(null);
const currentMatchPropUses = ref([]);
const usedProps = reactive({
  [MATCH3_PROP.SHUFFLE]: 0,
  [MATCH3_PROP.BOMB]: 0
});
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

let timerId = null;
/** 棋盘动画/结算中（交换、下落、连击、补满等） */
const animating = ref(false);
/** 连锁消除与计分结算中 */
const boardResolving = ref(false);
/** 递增以作废进行中的结算协程，防止重开后旧分数写入新对局 */
let resolutionGeneration = 0;

const gameConfig = computed(() => getMatch3DifficultyConfig());
const clientConfig = computed(() => getMatch3ClientConfig());
const animationConfig = computed(() => ({
  swapMs: clientConfig.value?.animation?.swapMs ?? 180,
  removeMs: clientConfig.value?.animation?.removeMs ?? 220,
  dropMs: clientConfig.value?.animation?.dropMs ?? 260,
  chainDelayMs: clientConfig.value?.animation?.chainDelayMs ?? 120
}));
const isGameInProgress = computed(
  () => gameStatus.value === 'playing' || gameStatus.value === 'paused'
);
const canBoardInteract = computed(
  () => gameStatus.value === 'idle' || gameStatus.value === 'playing'
);
const inputLocked = computed(
  () => !canBoardInteract.value || animating.value || resultModal.visible
);
const canUseProps = computed(() => gameStatus.value === 'playing' && !animating.value);
const canRestartGame = computed(() => !animating.value && !boardResolving.value);
const rankingSubtitle = computed(() =>
  mode.value === 'timed'
    ? '限时模式 · 全服前十名（按成绩排序）'
    : '无限模式 · 全服前十名（按成绩排序）'
);

const inventoryDisabledProps = computed(() => ({
  [MATCH3_PROP.SHUFFLE]:
    !canUseProps.value ||
    propQuantity(MATCH3_PROP.SHUFFLE) <= 0 ||
    propRemaining(MATCH3_PROP.SHUFFLE) <= 0,
  [MATCH3_PROP.BOMB]:
    !canUseProps.value ||
    propQuantity(MATCH3_PROP.BOMB) <= 0 ||
    propRemaining(MATCH3_PROP.BOMB) <= 0
}));

const inventoryUseLabels = computed(() => ({
  [MATCH3_PROP.SHUFFLE]: '使用',
  [MATCH3_PROP.BOMB]: activeTool.value === 'bomb' ? '取消' : '使用'
}));

const propQuotas = computed(() => [
  {
    label: '洗牌',
    used: propRemaining(MATCH3_PROP.SHUFFLE),
    max: propLimit(MATCH3_PROP.SHUFFLE),
    themeSeed: 'violet'
  },
  {
    label: '炸弹',
    used: propRemaining(MATCH3_PROP.BOMB),
    max: propLimit(MATCH3_PROP.BOMB),
    themeSeed: 'orange'
  }
]);

useGameSwitchLock(isGameInProgress);

/**
 * @param {number} ms
 * @returns {Promise<void>}
 */
function wait(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

/**
 * 等待两帧，确保 CSS transition 生效
 * @returns {Promise<void>}
 */
function nextFrame() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(resolve);
    });
  });
}

/**
 * @returns {number}
 */
function cellStride() {
  return Number(clientConfig.value?.cellSize || 44) + CELL_GAP;
}

/**
 * @param {object[][]} grid
 * @returns {boolean}
 */
function hasEmptyCells(grid) {
  return grid.some((row) => row.some((cell) => !cell));
}

/**
 * @param {string} message
 * @param {string} [level]
 */
function showToast(message, level = 'info') {
  toastService.push(message, level);
}

/**
 * 确保 session 已创建
 */
function ensureSession() {
  if (!matchSessionId.value) {
    matchSessionId.value = session.newMatchSessionId();
    currentMatchPropUses.value = [];
  }
}

/**
 * @param {string} modeValue
 * @returns {number}
 */
function modeTimeLimit(modeValue) {
  return Number(gameConfig.value?.modes?.[modeValue]?.timeLimitSec || 0);
}

/**
 * @returns {number}
 */
function rewardForScore() {
  const settlement = gameConfig.value?.settlement || {};
  const reward = Math.floor(score.value * Number(settlement.rewardRate || 0));
  return Math.max(Number(settlement.minReward || 0), reward);
}

/**
 * 停止计时
 */
function stopTimer() {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
  }
}

/**
 * 启动计时
 */
function startTimer() {
  stopTimer();
  timerId = setInterval(() => {
    elapsedSec.value++;
    if (mode.value === 'timed') {
      remainingSec.value = Math.max(0, remainingSec.value - 1);
      if (remainingSec.value <= 0) {
        settleGame(false);
      }
    }
  }, 1000);
}

/**
 * 重置运行时状态
 * @param {string} [message]
 */
function resetRuntime(message) {
  stopTimer();
  activeTool.value = '';
  cellVisuals.value = {};
  chainHint.value = '';
  gameStatus.value = 'idle';
  score.value = 0;
  moves.value = 0;
  comboMax.value = 0;
  elapsedSec.value = 0;
  remainingSec.value = modeTimeLimit(mode.value);
  matchSessionId.value = null;
  currentMatchPropUses.value = [];
  usedProps[MATCH3_PROP.SHUFFLE] = 0;
  usedProps[MATCH3_PROP.BOMB] = 0;
  animating.value = false;
  boardResolving.value = false;
  gameMessage.value = message || '拖动方块交换即可开始';
}

/**
 * @returns {boolean}
 */
function isResolutionStale(gen) {
  return gen !== resolutionGeneration;
}

/**
 * 生成新棋盘并回到 idle，不启动计时、不写对局记录。
 * @param {string} [message]
 */
function setupBoard(message) {
  board.value = createBoard(gameConfig.value);
  resetRuntime(message);
}

/**
 * idle 下第一次有效操作时启动对局与计时。
 */
function startMatchIfIdle() {
  if (gameStatus.value !== 'idle') {
    return;
  }
  ensureSession();
  gameStatus.value = 'playing';
  startTimer();
  gameMessage.value = '对局已开始，继续消除方块吧';
}

/**
 * 重新生成棋盘并重置本局数据；结算中禁止执行。
 */
function restartGame() {
  if (!canRestartGame.value) {
    showToast('棋盘结算中，请稍候再重新开始', 'warning');
    return;
  }
  resolutionGeneration++;
  setupBoard('已重新生成棋盘，拖动方块交换即可开始');
}

/**
 * @param {string} value
 */
async function changeMode(value) {
  if (!canRestartGame.value) {
    showToast('棋盘结算中，请稍候再切换模式', 'warning');
    return;
  }
  if (isGameInProgress.value) {
    showToast('对局进行中，请先结束当前对局', 'warning');
    return;
  }
  mode.value = value;
  setupBoard(
    value === 'timed'
      ? '限时模式，首次有效交换后开始倒计时'
      : '无限模式，首次有效交换后开始计时'
  );
  await activateGame(MATCH3, {
    difficultyCode: difficultyCode.value,
    mode: value,
    includeInventory: true
  });
}

/**
 * @param {{ row: number; col: number }} from
 * @param {{ row: number; col: number }} to
 * @param {boolean} revert
 * @returns {Promise<void>}
 */
async function playSwapAnimation(from, to, revert) {
  const a = board.value[from.row]?.[from.col];
  const b = board.value[to.row]?.[to.col];
  if (!a || !b) {
    return;
  }
  const stride = cellStride();
  const dx = (to.col - from.col) * stride;
  const dy = (to.row - from.row) * stride;
  const ms = animationConfig.value.swapMs;

  cellVisuals.value = {
    [a.id]: { translateX: 0, translateY: 0 },
    [b.id]: { translateX: 0, translateY: 0 }
  };
  await nextFrame();
  cellVisuals.value = {
    [a.id]: { translateX: dx, translateY: dy },
    [b.id]: { translateX: -dx, translateY: -dy }
  };
  await wait(ms);

  if (revert) {
    cellVisuals.value = {
      [a.id]: { translateX: 0, translateY: 0 },
      [b.id]: { translateX: 0, translateY: 0 }
    };
    await wait(ms);
  }
  cellVisuals.value = {};
}

/**
 * @param {object[]} cells
 * @returns {Promise<void>}
 */
async function playRemoveAnimation(cells) {
  const ms = animationConfig.value.removeMs;
  const visuals = {};
  for (const cell of cells || []) {
    if (cell?.id) {
      visuals[cell.id] = { effect: 'removing', translateX: 0, translateY: 0 };
    }
  }
  cellVisuals.value = visuals;
  await wait(ms);
  cellVisuals.value = {};
}

/**
 * @param {object[]} drops
 * @param {object[][]} nextBoard
 * @returns {Promise<void>}
 */
async function playDropAnimation(drops, nextBoard) {
  const ms = animationConfig.value.dropMs;
  const stride = cellStride();
  const visuals = {};
  for (const drop of drops || []) {
    const fromRow = drop.from?.row ?? drop.fromRow;
    const toRow = drop.to?.row ?? drop.toRow;
    const deltaY = (fromRow - toRow) * stride;
    visuals[drop.id] = { translateX: 0, translateY: deltaY };
  }
  board.value = cloneBoard(nextBoard);
  cellVisuals.value = visuals;
  await nextFrame();
  const cleared = {};
  for (const id of Object.keys(visuals)) {
    cleared[id] = { translateX: 0, translateY: 0 };
  }
  cellVisuals.value = cleared;
  await wait(ms);
  cellVisuals.value = {};
}

/**
 * @param {object[]} spawns
 * @param {object[][]} nextBoard
 * @returns {Promise<void>}
 */
async function playSpawnAnimation(spawns, nextBoard) {
  const ms = animationConfig.value.dropMs;
  const stride = cellStride();
  const visuals = {};
  for (const spawn of spawns || []) {
    const fromRow = spawn.from?.row ?? spawn.fromRow;
    const toRow = spawn.to?.row ?? spawn.toRow;
    const deltaY = (fromRow - toRow) * stride;
    visuals[spawn.id] = { translateX: 0, translateY: deltaY };
  }
  board.value = cloneBoard(nextBoard);
  cellVisuals.value = visuals;
  await nextFrame();
  const cleared = {};
  for (const id of Object.keys(visuals)) {
    cleared[id] = { translateX: 0, translateY: 0 };
  }
  cellVisuals.value = cleared;
  await wait(ms);
  cellVisuals.value = {};
}

/**
 * @param {object[][]} working
 * @returns {Promise<object[][]>}
 */
async function playCollapseAndFill(working) {
  const collapsed = collapseBoard(working);
  if (collapsed.drops.length) {
    await playDropAnimation(collapsed.drops, collapsed.board);
    working = collapsed.board;
  } else if (hasEmptyCells(working)) {
    board.value = cloneBoard(collapsed.board);
    working = collapsed.board;
  }
  const filled = fillBoardControlled(working, gameConfig.value, score.value);
  if (filled.spawns.length) {
    await playSpawnAnimation(filled.spawns, filled.board);
    working = filled.board;
  } else {
    board.value = cloneBoard(filled.board);
    working = filled.board;
  }
  return working;
}

/**
 * 连锁消除动画（下落、补满与计分）
 * @param {object[][]} startBoard
 * @param {boolean} countMove
 * @returns {Promise<{ deadBoard: boolean; comboCount: number; scoreDelta: number }>}
 */
async function animateBoardResolution(startBoard, countMove) {
  const gen = resolutionGeneration;
  animating.value = true;
  boardResolving.value = true;
  let working = cloneBoard(startBoard);
  let fillScore = score.value;
  let scoreDelta = 0;
  let comboCount = 0;

  try {
    for (let guard = 0; guard < 40; guard++) {
      if (isResolutionStale(gen)) {
        return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
      }

      const matches = findMatches(working);
      if (matches.length) {
        comboCount++;
        chainHint.value = comboCount > 1 ? `连锁 x${comboCount}` : '';
        await wait(animationConfig.value.chainDelayMs);
        if (isResolutionStale(gen)) {
          return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
        }
        scoreDelta += scoreMatches(matches, gameConfig.value, comboCount);

        const removed = removeMatches(working, matches);
        await playRemoveAnimation(removed.removedCells);
        if (isResolutionStale(gen)) {
          return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
        }
        working = removed.board;
        board.value = cloneBoard(working);

        const collapsed = collapseBoard(working);
        if (collapsed.drops.length) {
          await playDropAnimation(collapsed.drops, collapsed.board);
          if (isResolutionStale(gen)) {
            return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
          }
          working = collapsed.board;
        } else {
          board.value = cloneBoard(collapsed.board);
          working = collapsed.board;
        }

        fillScore = score.value + scoreDelta;
        const filled = fillBoardControlled(working, gameConfig.value, fillScore);
        if (filled.spawns.length) {
          await playSpawnAnimation(filled.spawns, filled.board);
          if (isResolutionStale(gen)) {
            return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
          }
          working = filled.board;
        } else {
          board.value = cloneBoard(filled.board);
          working = filled.board;
        }
        continue;
      }

      if (hasEmptyCells(working)) {
        working = await playCollapseAndFill(working);
        if (isResolutionStale(gen)) {
          return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
        }
        continue;
      }
      break;
    }

    if (isResolutionStale(gen)) {
      return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
    }

    board.value = working;
    const deadBoard = !hasAvailableMove(working);
    if (countMove) {
      moves.value++;
    }
    score.value += scoreDelta;
    comboMax.value = Math.max(comboMax.value, comboCount);
    chainHint.value = '';
    cellVisuals.value = {};

    return {
      deadBoard,
      comboCount,
      scoreDelta,
      aborted: false
    };
  } finally {
    if (!isResolutionStale(gen)) {
      boardResolving.value = false;
      animating.value = false;
    }
  }
}

/**
 * @param {{ from: { row: number; col: number }; to: { row: number; col: number } }} payload
 */
async function handleSwapRequest(payload) {
  if (inputLocked.value) {
    return;
  }
  const from = payload.from;
  const to = payload.to;
  if (from.row === to.row && from.col === to.col) {
    return;
  }

  const gen = resolutionGeneration;
  animating.value = true;
  if (!canSwap(board.value, from, to)) {
    await playSwapAnimation(from, to, true);
    if (!isResolutionStale(gen)) {
      animating.value = false;
    }
    gameMessage.value = '该交换无法形成消除';
    return;
  }

  startMatchIfIdle();
  await playSwapAnimation(from, to, false);
  if (isResolutionStale(gen)) {
    return;
  }
  const swapped = swapCells(board.value, from, to);
  board.value = swapped.board;

  const result = await animateBoardResolution(swapped.board, true);
  if (result.aborted || isResolutionStale(gen)) {
    return;
  }
  if (result.deadBoard) {
    await settleGame(true);
  } else {
    gameMessage.value =
      result.comboCount > 0
        ? `+${result.scoreDelta} 分`
        : '继续拖动方块消除吧';
  }
}

/**
 * @param {object} cell
 */
async function handleBombCellClick(cell) {
  if (inputLocked.value || activeTool.value !== 'bomb') {
    return;
  }
  await applyBombProp(cell);
}

/**
 * @param {string} propCode
 * @returns {number}
 */
function propLimit(propCode) {
  const fromMode = getMatch3ModePropLimit(mode.value, propCode);
  return fromMode != null ? fromMode : 0;
}

/**
 * 本局道具剩余可用次数。
 * @param {string} propCode
 * @returns {number}
 */
function propRemaining(propCode) {
  return Math.max(0, propLimit(propCode) - usedProps[propCode]);
}

/**
 * @param {string} propCode
 * @returns {number}
 */
function propQuantity(propCode) {
  return propQuantities.value[propCode] || 0;
}

/**
 * @param {string} propCode
 * @param {string} label
 */
function recordPropUsage(propCode, label) {
  ensureSession();
  session.trackPropUsage(currentMatchPropUses.value, {
    propCode,
    label,
    timerSec: elapsedSec.value,
    sessionId: matchSessionId.value
  });
  session.persistLocal();
}

/**
 * @param {string} propCode
 */
async function useProp(propCode) {
  if (!canUseProps.value) {
    showToast('请等待动画结束后再使用道具', 'warning');
    return;
  }
  if (propQuantity(propCode) <= 0) {
    showToast('道具数量不足', 'warning');
    return;
  }
  if (propRemaining(propCode) <= 0) {
    showToast('本局道具使用次数已达上限', 'warning');
    return;
  }
  if (propCode === MATCH3_PROP.SHUFFLE) {
    await applyShuffleProp();
    return;
  }
  if (propCode === MATCH3_PROP.BOMB) {
    activeTool.value = 'bomb';
    gameMessage.value = '点击棋盘格子使用炸弹';
  }
}

/**
 * 应用洗牌道具
 */
async function applyShuffleProp() {
  const gen = resolutionGeneration;
  animating.value = true;
  usedProps[MATCH3_PROP.SHUFFLE]++;
  recordPropUsage(MATCH3_PROP.SHUFFLE, '对局内使用洗牌道具');
  const rule = getMatch3PropRule(MATCH3_PROP.SHUFFLE)?.rule || {};
  const shuffled = shuffleBoard(board.value, {
    ...gameConfig.value,
    allowMatchesAfterShuffle: rule.allowMatchesAfterShuffle,
    requireAtLeastOneMove: rule.requireAtLeastOneMove
  });
  board.value = shuffled.board;
  const visuals = {};
  for (const cell of board.value.flat().filter(Boolean)) {
    visuals[cell.id] = { effect: 'shuffle', translateX: 0, translateY: 0 };
  }
  cellVisuals.value = visuals;
  await wait(380);
  if (isResolutionStale(gen)) {
    return;
  }
  cellVisuals.value = {};
  animating.value = false;
  gameMessage.value = hasAvailableMove(board.value)
    ? '洗牌完成'
    : '洗牌后仍无可行步';
}

/**
 * @param {object} cell
 */
async function applyBombProp(cell) {
  const gen = resolutionGeneration;
  activeTool.value = '';
  usedProps[MATCH3_PROP.BOMB]++;
  recordPropUsage(MATCH3_PROP.BOMB, '使用炸弹清除 3x3 区域');
  const radius = Number(getMatch3PropRule(MATCH3_PROP.BOMB)?.rule?.radius || 1);
  const bombed = applyBomb(board.value, cell.row, cell.col, radius);

  animating.value = true;
  let working = cloneBoard(bombed.board);
  board.value = working;
  await playRemoveAnimation(bombed.removedCells);
  if (isResolutionStale(gen)) {
    return;
  }
  working = await playCollapseAndFill(working);
  if (isResolutionStale(gen)) {
    return;
  }

  const result = await animateBoardResolution(working, true);
  if (result.aborted || isResolutionStale(gen)) {
    return;
  }
  if (result.deadBoard) {
    await settleGame(true);
  } else {
    gameMessage.value =
      result.comboCount > 0
        ? `+${result.scoreDelta} 分`
        : '继续拖动方块消除吧';
  }
}

/**
 * 结束当前对局
 */
async function endCurrentGame() {
  if (gameStatus.value === 'idle') {
    showToast('尚未开始对局', 'info');
    return;
  }
  if (gameStatus.value === 'ended') {
    return;
  }
  await settleGame(false);
}

/**
 * @param {boolean} deadBoard
 */
async function settleGame(deadBoard) {
  if (gameStatus.value === 'ended') {
    return;
  }
  ensureSession();
  gameStatus.value = 'ended';
  stopTimer();
  const reward = rewardForScore();
  const payload = {
    comboMax: comboMax.value,
    moves: moves.value,
    deadBoard
  };
  const matchPayload = {
    ...payload,
    controlledRandomVersion: 1
  };
  await session.settleWin({
    score: score.value,
    rewardScore: reward,
    difficultyCode: difficultyCode.value,
    durationMs: Math.round(elapsedSec.value * 1000),
    propUses: currentMatchPropUses.value,
    sessionId: matchSessionId.value,
    mode: mode.value,
    matchPayload,
    scorePayload: payload
  });
  openResultModal(deadBoard, reward);
  gameMessage.value = deadBoard ? '棋盘无解，对局结束' : '对局已结束';
}

/**
 * @param {boolean} deadBoard
 * @param {number} reward
 */
function openResultModal(deadBoard, reward) {
  const timed = mode.value === 'timed';
  const highlights = [
    { label: '最大连击', value: comboMax.value },
    { label: '洗牌道具', value: `${usedProps[MATCH3_PROP.SHUFFLE]} 次` },
    { label: '炸弹道具', value: `${usedProps[MATCH3_PROP.BOMB]} 次` }
  ];
  Object.assign(resultModal, {
    visible: true,
    title: '本局结算',
    subtitle: deadBoard ? '棋盘已无可用步数，对局结束' : '对局已结束',
    resultType: deadBoard ? 'failed' : 'neutral',
    stats: [
      { label: '最终分数', value: score.value },
      { label: '模式', value: timed ? '限时' : '无尽' },
      { label: '难度', value: getDifficultyName(MATCH3, difficultyCode.value) },
      { label: '用时', value: formatDurationMmSs(elapsedSec.value) },
      { label: '步数', value: moves.value }
    ],
    rewards: [{ label: '平台积分', value: `+${reward}` }],
    highlights,
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
    restartGame();
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

/**
 * 页面可见性变化时暂停/恢复计时。
 */
function onVisibilityChange() {
  if (document.hidden) {
    if (gameStatus.value !== 'playing') {
      return;
    }
    stopTimer();
    gameStatus.value = 'paused';
    gameMessage.value = '页面隐藏，计时已暂停';
    return;
  }
  if (gameStatus.value !== 'paused') {
    return;
  }
  gameStatus.value = 'playing';
  startTimer();
  gameMessage.value = '对局已继续';
}

onMounted(async () => {
  platform.setCurrentGame(MATCH3);
  await activateGame(MATCH3, {
    difficultyCode: difficultyCode.value,
    mode: mode.value,
    includeInventory: true
  });
  setupBoard('限时模式，首次有效交换后开始倒计时');
  document.addEventListener('visibilitychange', onVisibilityChange);
});

onBeforeUnmount(() => {
  stopTimer();
  document.removeEventListener('visibilitychange', onVisibilityChange);
});
</script>

<style scoped>
.match3-chain-hint {
  position: absolute;
  top: 0;
  z-index: 2;
  padding: 8px 16px;
  border-radius: 999px;
  color: #fff7ed;
  background: rgba(249, 115, 22, 0.86);
  animation: match3Hint 420ms ease;
}

@keyframes match3Hint {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
