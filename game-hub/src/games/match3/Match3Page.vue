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
            :started="gameStarted"
            :in-progress="isGameInProgress"
            :locked="isGameInProgress"
            message=""
            @change-mode="changeMode"
            @start="startOrRestartGame"
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
          :difficulty-code="DIFFICULTY"
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
            :started="gameStarted"
            :in-progress="isGameInProgress"
            :locked="isGameInProgress"
            :message="gameMessage"
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
          :usable-props="['match3_shuffle', 'match3_bomb']"
          :active-prop="activeTool === 'bomb' ? 'match3_bomb' : ''"
          :disabled-props="inventoryDisabledProps"
          :use-labels="inventoryUseLabels"
          @use-prop="useProp"
        />
      </template>
    </GamePlayLayout>

    <Match3ResultModal
      :visible="resultModal.visible"
      :mode="mode"
      :score="resultModal.score"
      :reward="resultModal.reward"
      :moves="resultModal.moves"
      :combo-max="resultModal.comboMax"
      :dead-board="resultModal.deadBoard"
      @close="resultModal.visible = false"
    />
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import Match3Board from './components/Match3Board.vue';
import Match3Hud from './components/Match3Hud.vue';
import Match3ResultModal from './components/Match3ResultModal.vue';
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
import { getMatch3ClientConfig, getMatch3DifficultyConfig, getMatch3PropRule } from './match3Config.js';
import { GH_MINESWEEPER_SESSION_LOCK } from '../../constants/injectionKeys.js';
import { createGameSession } from '../../services/gameSessionService.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import * as toastService from '../../services/toastService.js';
import { usePlatformStore } from '../../stores/platformStore.js';

const MATCH3 = 'match3';
const DIFFICULTY = 'normal';
const configPanelTitle = '\u6e38\u620f\u4fe1\u606f';
const CELL_GAP = 6;
const session = createGameSession({ gameCode: MATCH3 });
const platform = usePlatformStore();
const user = session.currentUser;
const sessionLockApi = inject(GH_MINESWEEPER_SESSION_LOCK, null);

const mode = ref('timed');
const board = ref([]);
const activeTool = ref('');
const cellVisuals = ref({});
const chainHint = ref('');
const gameStarted = ref(false);
const gameOver = ref(false);
const score = ref(0);
const moves = ref(0);
const comboMax = ref(0);
const elapsedSec = ref(0);
const remainingSec = ref(180);
const gameMessage = ref('\u9009\u62e9\u6a21\u5f0f\u5e76\u5f00\u59cb\u6e38\u620f');
const matchSessionId = ref(null);
const currentMatchPropUses = ref([]);
const usedProps = reactive({
  match3_shuffle: 0,
  match3_bomb: 0
});
const resultModal = reactive({
  visible: false,
  score: 0,
  reward: 0,
  moves: 0,
  comboMax: 0,
  deadBoard: false
});

let timerId = null;
const animating = ref(false);

const gameConfig = computed(() => getMatch3DifficultyConfig());
const clientConfig = computed(() => getMatch3ClientConfig());
const animationConfig = computed(() => ({
  swapMs: clientConfig.value?.animation?.swapMs ?? 180,
  removeMs: clientConfig.value?.animation?.removeMs ?? 220,
  dropMs: clientConfig.value?.animation?.dropMs ?? 260,
  chainDelayMs: clientConfig.value?.animation?.chainDelayMs ?? 120
}));
const isGameInProgress = computed(() => gameStarted.value && !gameOver.value);
const inputLocked = computed(
  () => !isGameInProgress.value || animating.value || resultModal.visible
);
const canUseProps = computed(() => isGameInProgress.value && !animating.value);
const rankingSubtitle = computed(() =>
  mode.value === 'timed'
    ? '\u9650\u65f6\u6a21\u5f0f \u00b7 \u5168\u670d\u524d\u5341\u540d\uff08\u6309\u6210\u7ee9\u6392\u5e8f\uff09'
    : '\u65e0\u9650\u6a21\u5f0f \u00b7 \u5168\u670d\u524d\u5341\u540d\uff08\u6309\u6210\u7ee9\u6392\u5e8f\uff09'
);

const inventoryDisabledProps = computed(() => ({
  match3_shuffle:
    !canUseProps.value ||
    (user.value.props?.match3Shuffle || 0) <= 0 ||
    usedProps.match3_shuffle >= propLimit('match3_shuffle'),
  match3_bomb:
    !canUseProps.value ||
    (user.value.props?.match3Bomb || 0) <= 0 ||
    usedProps.match3_bomb >= propLimit('match3_bomb')
}));

const inventoryUseLabels = computed(() => ({
  match3_bomb: activeTool.value === 'bomb' ? '\u53d6\u6d88' : '\u4f7f\u7528'
}));

watch(
  isGameInProgress,
  (value) => {
    sessionLockApi?.setLocked?.(value);
  },
  { immediate: true }
);

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
 * ??????? CSS transition ???
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
 * ???? session ????
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
 * ??????
 */
function stopTimer() {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
  }
}

/**
 * ??????
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
 * ????????
 * @param {string} [message]
 */
function resetRuntime(message) {
  stopTimer();
  activeTool.value = '';
  cellVisuals.value = {};
  chainHint.value = '';
  gameStarted.value = false;
  gameOver.value = false;
  score.value = 0;
  moves.value = 0;
  comboMax.value = 0;
  elapsedSec.value = 0;
  remainingSec.value = modeTimeLimit(mode.value);
  matchSessionId.value = null;
  currentMatchPropUses.value = [];
  usedProps.match3_shuffle = 0;
  usedProps.match3_bomb = 0;
  animating.value = false;
  gameMessage.value = message || '\u9009\u62e9\u6a21\u5f0f\u5e76\u5f00\u59cb';
}

/**
 * ??????
 * @param {string} [message]
 */
function setupBoard(message) {
  board.value = createBoard(gameConfig.value);
  resetRuntime(message);
}

/**
 * ??????????
 */
function startOrRestartGame() {
  setupBoard('\u6309\u4f4f\u65b9\u5757\u5e76\u5411\u76f8\u90bb\u65b9\u5411\u62d6\u52a8\u4ea4\u6362');
  ensureSession();
  gameStarted.value = true;
  startTimer();
}

/**
 * @param {string} value
 */
async function changeMode(value) {
  if (isGameInProgress.value) {
    showToast('\u5bf9\u5c40\u8fdb\u884c\u4e2d\uff0c\u8bf7\u5148\u7ed3\u675f\u5f53\u524d\u5bf9\u5c40', 'warning');
    return;
  }
  mode.value = value;
  setupBoard(
    value === 'timed' ? '\u9650\u65f6\u6a21\u5f0f\uff0c180 \u79d2\u5012\u8ba1\u65f6' : '\u65e0\u9650\u6a21\u5f0f\uff0c\u70b9\u51fb\u5f00\u59cb\u6e38\u620f'
  );
  await activateGame(MATCH3, {
    difficultyCode: DIFFICULTY,
    mode: value,
    includeLeaderboard: true,
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
 * ??????????????????
 * @param {object[][]} startBoard
 * @param {boolean} countMove
 * @returns {Promise<{ deadBoard: boolean; comboCount: number; scoreDelta: number }>}
 */
async function animateBoardResolution(startBoard, countMove) {
  animating.value = true;
  let working = cloneBoard(startBoard);
  let fillScore = score.value;
  let scoreDelta = 0;
  let comboCount = 0;

  for (let guard = 0; guard < 40; guard++) {
    const matches = findMatches(working);
    if (matches.length) {
      comboCount++;
      chainHint.value = comboCount > 1 ? `\u8fde\u9501 x${comboCount}` : '';
      await wait(animationConfig.value.chainDelayMs);
      scoreDelta += scoreMatches(matches, gameConfig.value, comboCount);

      const removed = removeMatches(working, matches);
      await playRemoveAnimation(removed.removedCells);
      working = removed.board;
      board.value = cloneBoard(working);

      const collapsed = collapseBoard(working);
      if (collapsed.drops.length) {
        await playDropAnimation(collapsed.drops, collapsed.board);
        working = collapsed.board;
      } else {
        board.value = cloneBoard(collapsed.board);
        working = collapsed.board;
      }

      fillScore = score.value + scoreDelta;
      const filled = fillBoardControlled(working, gameConfig.value, fillScore);
      if (filled.spawns.length) {
        await playSpawnAnimation(filled.spawns, filled.board);
        working = filled.board;
      } else {
        board.value = cloneBoard(filled.board);
        working = filled.board;
      }
      continue;
    }

    if (hasEmptyCells(working)) {
      working = await playCollapseAndFill(working);
      continue;
    }
    break;
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
  animating.value = false;

  return {
    deadBoard,
    comboCount,
    scoreDelta
  };
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

  animating.value = true;
  if (!canSwap(board.value, from, to)) {
    await playSwapAnimation(from, to, true);
    animating.value = false;
    gameMessage.value = '\u8be5\u4ea4\u6362\u65e0\u6cd5\u5f62\u6210\u6d88\u9664';
    return;
  }

  await playSwapAnimation(from, to, false);
  const swapped = swapCells(board.value, from, to);
  board.value = swapped.board;

  const result = await animateBoardResolution(swapped.board, true);
  if (result.deadBoard) {
    await settleGame(true);
  } else {
    gameMessage.value =
      result.comboCount > 0
        ? `+${result.scoreDelta} \u5206`
        : '\u7ee7\u7eed\u62d6\u52a8\u65b9\u5757\u6d88\u9664\u5427';
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
  return Number(getMatch3PropRule(propCode)?.maxUsePerMatch || 0);
}

/**
 * @param {string} propCode
 * @returns {number}
 */
function propQuantity(propCode) {
  if (propCode === 'match3_shuffle') {
    return user.value.props?.match3Shuffle || 0;
  }
  if (propCode === 'match3_bomb') {
    return user.value.props?.match3Bomb || 0;
  }
  return 0;
}

/**
 * @param {string} propCode
 * @param {string} label
 */
function recordPropUsage(propCode, label) {
  ensureSession();
  session.trackPropUsage(currentMatchPropUses.value, {
    type: propCode,
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
    showToast('\u8bf7\u7b49\u5f85\u52a8\u753b\u7ed3\u675f\u540e\u518d\u4f7f\u7528\u9053\u5177', 'warning');
    return;
  }
  if (propQuantity(propCode) <= 0) {
    showToast('\u9053\u5177\u6570\u91cf\u4e0d\u8db3', 'warning');
    return;
  }
  if (usedProps[propCode] >= propLimit(propCode)) {
    showToast('\u672c\u5c40\u9053\u5177\u4f7f\u7528\u6b21\u6570\u5df2\u8fbe\u4e0a\u9650', 'warning');
    return;
  }
  if (propCode === 'match3_shuffle') {
    await applyShuffleProp();
    return;
  }
  if (propCode === 'match3_bomb') {
    activeTool.value = 'bomb';
    gameMessage.value = '\u70b9\u51fb\u68cb\u76d8\u683c\u5b50\u4f7f\u7528\u70b8\u5f39';
  }
}

/**
 * ???????
 */
async function applyShuffleProp() {
  animating.value = true;
  usedProps.match3_shuffle++;
  recordPropUsage('match3_shuffle', '\u5bf9\u5c40\u5185\u4f7f\u7528\u6d17\u724c\u9053\u5177');
  const rule = getMatch3PropRule('match3_shuffle')?.rule || {};
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
  cellVisuals.value = {};
  animating.value = false;
  gameMessage.value = hasAvailableMove(board.value)
    ? '\u6d17\u724c\u5b8c\u6210'
    : '\u6d17\u724c\u540e\u4ecd\u65e0\u53ef\u884c\u6b65';
}

/**
 * @param {object} cell
 */
async function applyBombProp(cell) {
  activeTool.value = '';
  usedProps.match3_bomb++;
  recordPropUsage('match3_bomb', '\u4f7f\u7528\u70b8\u5f39\u6e05\u9664 3x3 \u533a\u57df');
  const radius = Number(getMatch3PropRule('match3_bomb')?.rule?.radius || 1);
  const bombed = applyBomb(board.value, cell.row, cell.col, radius);

  animating.value = true;
  let working = cloneBoard(bombed.board);
  board.value = working;
  await playRemoveAnimation(bombed.removedCells);
  working = await playCollapseAndFill(working);

  const result = await animateBoardResolution(working, true);
  if (result.deadBoard) {
    await settleGame(true);
  } else {
    gameMessage.value =
      result.comboCount > 0
        ? `+${result.scoreDelta} \u5206`
        : '\u7ee7\u7eed\u62d6\u52a8\u65b9\u5757\u6d88\u9664\u5427';
  }
}

/**
 * ???????
 */
async function endCurrentGame() {
  if (!isGameInProgress.value) {
    return;
  }
  await settleGame(false);
}

/**
 * @param {boolean} deadBoard
 */
async function settleGame(deadBoard) {
  if (gameOver.value) {
    return;
  }
  ensureSession();
  gameOver.value = true;
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
    difficulty: DIFFICULTY,
    timeSec: elapsedSec.value,
    propUses: currentMatchPropUses.value,
    sessionId: matchSessionId.value,
    mode: mode.value,
    matchPayload,
    scorePayload: payload
  });
  resultModal.visible = true;
  resultModal.score = score.value;
  resultModal.reward = reward;
  resultModal.moves = moves.value;
  resultModal.comboMax = comboMax.value;
  resultModal.deadBoard = deadBoard;
  gameMessage.value = deadBoard ? '\u68cb\u76d8\u65e0\u89e3\uff0c\u5bf9\u5c40\u7ed3\u675f' : '\u5bf9\u5c40\u5df2\u7ed3\u675f';
}

/**
 * ??????????
 */
function pauseDueToPageHidden() {
  if (!isGameInProgress.value) {
    return;
  }
  stopTimer();
  gameMessage.value = '\u9875\u9762\u9690\u85cf\uff0c\u8ba1\u65f6\u5df2\u6682\u505c';
}

onMounted(async () => {
  platform.setCurrentGame(MATCH3);
  await activateGame(MATCH3, {
    difficultyCode: DIFFICULTY,
    mode: mode.value,
    includeLeaderboard: true,
    includeInventory: true
  });
  setupBoard('\u9650\u65f6\u6a21\u5f0f\uff0c180 \u79d2\u5012\u8ba1\u65f6');
  document.addEventListener('visibilitychange', pauseDueToPageHidden);
});

onBeforeUnmount(() => {
  sessionLockApi?.setLocked?.(false);
  stopTimer();
  document.removeEventListener('visibilitychange', pauseDueToPageHidden);
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
