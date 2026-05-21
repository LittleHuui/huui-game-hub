<template>
  <div>
    <GamePlayLayout>
      <template #config>
        <GameConfigPanel title="游戏信息">
          <Game2048Hud
            section="config"
            :game-status="gameStatus"
            :restart-disabled="!canStartOrRestartGame"
            :show-end-game="shouldShowEndGameButton"
            :can-end-game="canEndGame"
            @start-or-restart="startOrRestartGame"
            @end="endCurrentGame"
          />
        </GameConfigPanel>
      </template>

      <template #shop>
        <GameShopPanel :game-code="GAME2048_CODE" :session-id="matchSessionId" />
      </template>

      <template #ranking>
        <GameRankingPanel
          :game-code="GAME2048_CODE"
          :mode="GAME2048_MODE"
          :difficulty-code="difficultyCode"
          value-metric="score"
          subtitle="经典模式 · 全服前十名（按得分排序）"
        />
      </template>

      <template #hud>
        <GameHudPanel>
          <Game2048Hud
            section="hud"
            :score="score"
            :moves="moves"
            :max-tile="maxTile"
            :elapsed-sec="elapsedSec"
            :clear-cell-uses="clearCellUses"
            :score-penalty="scorePenalty"
            :reward-score="rewardScorePreview"
            :reached2048="reached2048Flag"
            :message="gameMessage"
            :prop-quotas="propQuotas"
            theme-seed="2048"
          />
        </GameHudPanel>
      </template>

      <template #board>
        <Game2048Board
          ref="boardComponentRef"
          :tiles="tiles"
          :select-mode="isPropSelecting"
          :move-input-locked="moveInputLocked"
          :board-style="boardAnimationStyle"
          :slide-offsets="slideOffsets"
          :new-tile-ids="newTileIds"
          :merged-tile-ids="mergedTileIds"
          :clearing-tile-id="clearingTileId"
          @move="handleMoveInput"
          @cell-select="handleClearCellSelect"
        />
      </template>

      <template #inventory>
        <GameInventoryPanel
          :game-code="GAME2048_CODE"
          :usable-props="[GAME2048_PROP.CLEAR_CELL]"
          :active-prop="activeTool === GAME2048_PROP.CLEAR_CELL ? GAME2048_PROP.CLEAR_CELL : ''"
          :disabled-props="inventoryDisabledProps"
          :use-labels="inventoryUseLabels"
          @use-prop="useProp"
        />
      </template>
    </GamePlayLayout>

    <Game2048ResultModal
      :visible="resultModal.visible"
      :score="resultModal.score"
      :reward="resultModal.reward"
      :moves="resultModal.moves"
      :max-tile="resultModal.maxTile"
      :reached2048="resultModal.reached2048"
      :clear-cell-uses="resultModal.clearCellUses"
      :score-penalty="resultModal.scorePenalty"
      :game-over="resultModal.gameOver"
      @close="resultModal.visible = false"
    />
  </div>
</template>

<script setup>
import './game2048.css';
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import Game2048Board from './components/Game2048Board.vue';
import Game2048Hud from './components/Game2048Hud.vue';
import Game2048ResultModal from './components/Game2048ResultModal.vue';
import GamePlayLayout from '../../components/game/GamePlayLayout.vue';
import GameConfigPanel from '../../components/game/GameConfigPanel.vue';
import GameShopPanel from '../../components/game/GameShopPanel.vue';
import GameRankingPanel from '../../components/game/GameRankingPanel.vue';
import GameHudPanel from '../../components/game/GameHudPanel.vue';
import GameInventoryPanel from '../../components/game/GameInventoryPanel.vue';
import {
  applyScorePenalty,
  calcClearPenalty,
  clearTile,
  createInitialTiles,
  getMaxTileFromTiles,
  hasReached2048Tiles,
  isGameOverTiles,
  moveTiles,
  spawnRandomTileOnTiles
} from './game2048Engine.js';
import {
  CLEAR_ANIMATION_MS,
  MERGE_ANIMATION_MS,
  MOVE_ANIMATION_MS,
  getGame2048AnimationCssVars,
  nextFrame,
  postSlideAnimationWaitMs
} from './game2048Animation.js';
import {
  GAME2048_CODE,
  GAME2048_MODE,
  GAME2048_PROP,
  getGame2048DifficultyConfig,
  getGame2048ModePropLimit
} from './game2048Config.js';
import { useGamePropQuantities } from '../../composables/useGamePropQuantities.js';
import { useGameSwitchLock } from '../../composables/useGameSwitchLock.js';
import { createGameSession } from '../../services/gameSessionService.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import * as toastService from '../../services/toastService.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import { getDefaultDifficultyCode } from '../../services/gameDifficultyService.js';

const session = createGameSession({ gameCode: GAME2048_CODE });
const platform = usePlatformStore();
const propQuantities = useGamePropQuantities(GAME2048_CODE);
const boardComponentRef = ref(null);

const difficultyCode = computed(
  () => getGame2048DifficultyConfig().difficultyCode || getDefaultDifficultyCode(GAME2048_CODE)
);

const tiles = ref(createInitialTiles());
const activeTool = ref('');
const gameStatus = ref('idle');
const score = ref(0);
const moves = ref(0);
const scorePenalty = ref(0);
const clearCellUses = ref(0);
const reached2048Flag = ref(false);
const elapsedSec = ref(0);
const gameMessage = ref('点击开始对局，或直接在棋盘用方向键 / WASD / 滑动开始');
const matchSessionId = ref(null);
const currentMatchPropUses = ref([]);
const usedClearCell = ref(0);
const isMoving = ref(false);
const isSettling = ref(false);
const isStarting = ref(false);
const slideOffsets = ref({});
const newTileIds = ref({});
const mergedTileIds = ref({});
const clearingTileId = ref(null);

const resultModal = reactive({
  visible: false,
  score: 0,
  reward: 0,
  moves: 0,
  maxTile: 0,
  reached2048: false,
  clearCellUses: 0,
  scorePenalty: 0,
  gameOver: true
});

let timerId = null;
/** 递增以作废进行中的移动动画，防止快速连按导致状态错乱 */
let moveGeneration = 0;

const gameConfig = computed(() => getGame2048DifficultyConfig());
const maxTile = computed(() => getMaxTileFromTiles(tiles.value));
const rewardScorePreview = computed(() => rewardForScore());
const isGameInProgress = computed(
  () => gameStatus.value === 'playing' || gameStatus.value === 'paused'
);
const boardAnimationStyle = getGame2048AnimationCssVars();

const isPropSelecting = computed(() => activeTool.value === GAME2048_PROP.CLEAR_CELL);

/** 开局、移动动画、结算动画期间锁定操作按钮 */
const isOperationLocked = computed(
  () => isStarting.value || isMoving.value || isSettling.value
);

const canAcceptMoveInput = computed(
  () =>
    gameStatus.value === 'playing' &&
    !isOperationLocked.value &&
    !isPropSelecting.value &&
    !resultModal.visible
);

/** 空闲时可滑动/按键自动开局；已结束、结算中、动画中、道具选择中锁定 */
const moveInputLocked = computed(
  () =>
    gameStatus.value === 'ended' ||
    gameStatus.value === 'settling' ||
    isOperationLocked.value ||
    isPropSelecting.value ||
    resultModal.visible
);

const canStartOrRestartGame = computed(
  () => !isOperationLocked.value && gameStatus.value !== 'settling'
);

const shouldShowEndGameButton = computed(
  () => gameStatus.value === 'playing' || gameStatus.value === 'settling'
);

const canEndGame = computed(
  () => gameStatus.value === 'playing' && !isOperationLocked.value
);

const canUseClearCell = computed(
  () =>
    !isOperationLocked.value &&
    gameStatus.value === 'playing' &&
    propRemaining(GAME2048_PROP.CLEAR_CELL) > 0
);

const inventoryDisabledProps = computed(() => ({
  [GAME2048_PROP.CLEAR_CELL]:
    !canUseClearCell.value || propQuantity(GAME2048_PROP.CLEAR_CELL) <= 0
}));

const inventoryUseLabels = computed(() => ({
  [GAME2048_PROP.CLEAR_CELL]:
    activeTool.value === GAME2048_PROP.CLEAR_CELL ? '取消' : '使用'
}));

const propQuotas = computed(() => [
  {
    label: '清除锤',
    used: propRemaining(GAME2048_PROP.CLEAR_CELL),
    max: propLimit(GAME2048_PROP.CLEAR_CELL)
  }
]);

useGameSwitchLock(isGameInProgress);

/**
 * @param {string} message
 * @param {string} [level]
 */
function showToast(message, level = 'info') {
  toastService.push(message, level);
}

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
 * 确保对局 session 已创建。
 */
function ensureSession() {
  if (!matchSessionId.value) {
    matchSessionId.value = session.newMatchSessionId();
    currentMatchPropUses.value = [];
  }
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
 * 停止计时。
 */
function stopTimer() {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
  }
}

/**
 * 启动计时。
 */
function startTimer() {
  stopTimer();
  timerId = setInterval(() => {
    elapsedSec.value++;
  }, 1000);
}

/**
 * 重置本局运行时状态。
 * @param {string} [message]
 */
function resetRuntime(message) {
  moveGeneration++;
  stopTimer();
  activeTool.value = '';
  gameStatus.value = 'idle';
  score.value = 0;
  moves.value = 0;
  scorePenalty.value = 0;
  clearCellUses.value = 0;
  reached2048Flag.value = false;
  elapsedSec.value = 0;
  matchSessionId.value = null;
  currentMatchPropUses.value = [];
  usedClearCell.value = 0;
  isMoving.value = false;
  isSettling.value = false;
  isStarting.value = false;
  slideOffsets.value = {};
  newTileIds.value = {};
  mergedTileIds.value = {};
  clearingTileId.value = null;
  gameMessage.value =
    message || '点击开始对局，或直接在棋盘用方向键 / WASD / 滑动开始';
}

/**
 * 初始化棋盘。
 * @param {string} [message]
 */
function setupBoard(message) {
  tiles.value = createInitialTiles();
  resetRuntime(message);
}

/**
 * @param {string} propCode
 * @returns {number}
 */
function propLimit(propCode) {
  const fromMode = getGame2048ModePropLimit(propCode);
  return fromMode != null ? fromMode : 0;
}

/**
 * @param {string} propCode
 * @returns {number}
 */
function propRemaining(propCode) {
  return Math.max(0, propLimit(propCode) - usedClearCell.value);
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
 * @param {number} gen
 * @returns {boolean}
 */
function isMoveStale(gen) {
  return gen !== moveGeneration;
}

/**
 * 由 engine 滑动结果构建像素位移（起始为 0，下一帧设为目标 delta 以触发 transition）。
 * @param {import('./game2048Engine.js').Game2048Slide[]} slides
 * @param {number} stridePx
 * @returns {Record<number, { dx: number; dy: number }>}
 */
function buildSlidePixelOffsets(slides, stridePx) {
  const map = {};
  for (const slide of slides || []) {
    map[slide.id] = {
      dx: (slide.toCol - slide.fromCol) * stridePx,
      dy: (slide.toRow - slide.fromRow) * stridePx
    };
  }
  return map;
}

/**
 * 标记合并格子 id。
 * @param {import('./game2048Engine.js').Game2048MergeMark[]} merges
 */
function markMergedTileIds(merges) {
  const marks = {};
  for (const m of merges || []) {
    marks[m.id] = true;
  }
  mergedTileIds.value = marks;
}

/**
 * 空闲时自动开局并继续本次移动；已结束不响应移动输入。
 * @param {import('./game2048Engine.js').Game2048Direction} direction
 */
async function handleMoveInput(direction) {
  if (isOperationLocked.value || isPropSelecting.value || resultModal.visible) {
    return;
  }
  if (gameStatus.value === 'ended' || gameStatus.value === 'settling') {
    return;
  }
  if (gameStatus.value === 'idle') {
    const started = await startGame();
    if (!started) {
      return;
    }
  }
  if (gameStatus.value !== 'playing') {
    return;
  }
  await handleMove(direction);
}

/**
 * idle 下首次方向输入自动开局：沿用当前预览棋盘，仅创建一次 session。
 * @returns {Promise<boolean>}
 */
async function startGame() {
  if (gameStatus.value !== 'idle') {
    return gameStatus.value === 'playing';
  }
  if (isStarting.value) {
    return false;
  }
  isStarting.value = true;
  try {
    resultModal.visible = false;
    ensureSession();
    gameStatus.value = 'playing';
    startTimer();
    gameMessage.value = '对局已开始，滑动棋盘继续';
    return true;
  } finally {
    isStarting.value = false;
  }
}

/**
 * @param {import('./game2048Engine.js').Game2048Direction} direction
 */
async function handleMove(direction) {
  if (!canAcceptMoveInput.value) {
    return;
  }
  const gen = ++moveGeneration;
  const beforeTiles = tiles.value;
  const result = moveTiles(beforeTiles, direction);
  if (!result.moved) {
    return;
  }

  const stridePx = boardComponentRef.value?.getCellStridePx?.() ?? 0;
  isMoving.value = true;
  mergedTileIds.value = {};
  newTileIds.value = {};

  try {
    tiles.value = beforeTiles;
    slideOffsets.value = {};
    await nextFrame();
    if (isMoveStale(gen)) {
      return;
    }
    slideOffsets.value = buildSlidePixelOffsets(result.slides, stridePx);
    await wait(MOVE_ANIMATION_MS);
    if (isMoveStale(gen)) {
      return;
    }

    slideOffsets.value = {};
    tiles.value = result.tiles;
    score.value += result.scoreDelta;
    moves.value += 1;
    if (hasReached2048Tiles(tiles.value)) {
      reached2048Flag.value = true;
    }

    if ((result.merges || []).length > 0) {
      markMergedTileIds(result.merges);
      await wait(MERGE_ANIMATION_MS);
      if (isMoveStale(gen)) {
        return;
      }
      mergedTileIds.value = {};
    }

    const spawnResult = spawnRandomTileOnTiles(tiles.value);
    tiles.value = spawnResult.tiles;
    if (spawnResult.spawn) {
      newTileIds.value = { [spawnResult.spawn.id]: true };
      await wait(postSlideAnimationWaitMs(false));
      if (isMoveStale(gen)) {
        return;
      }
      newTileIds.value = {};
    }

    if (isGameOverTiles(tiles.value)) {
      await settleGame(true);
      return;
    }
    gameMessage.value = '继续滑动合成更大数字';
  } finally {
    if (!isMoveStale(gen)) {
      isMoving.value = false;
    }
  }
}

/**
 * @param {string} propCode
 */
function useProp(propCode) {
  if (gameStatus.value === 'ended' || gameStatus.value === 'settling') {
    showToast('对局已结束，无法使用道具', 'warning');
    return;
  }
  if (!canUseClearCell.value && propCode === GAME2048_PROP.CLEAR_CELL) {
    if (gameStatus.value === 'idle') {
      showToast('请先开始一局再使用道具', 'warning');
    } else {
      showToast('请等待当前操作完成', 'warning');
    }
    return;
  }
  if (propCode !== GAME2048_PROP.CLEAR_CELL) {
    return;
  }
  if (propQuantity(propCode) <= 0) {
    showToast('道具数量不足', 'warning');
    return;
  }
  if (propRemaining(propCode) <= 0) {
    showToast('本局清除锤使用次数已达上限', 'warning');
    return;
  }
  if (activeTool.value === GAME2048_PROP.CLEAR_CELL) {
    activeTool.value = '';
    gameMessage.value = '已取消清除锤';
    return;
  }
  activeTool.value = GAME2048_PROP.CLEAR_CELL;
  gameMessage.value = '点击要清除的格子（非空格）';
  boardComponentRef.value?.focusBoard?.();
}

/**
 * @param {{ row: number; col: number }} pos
 */
async function handleClearCellSelect(pos) {
  if (!isPropSelecting.value || gameStatus.value !== 'playing' || isOperationLocked.value) {
    return;
  }
  const cleared = clearTile(tiles.value, pos.row, pos.col);
  if (!cleared.ok) {
    showToast('只能清除非空格子', 'warning');
    return;
  }
  isMoving.value = true;
  clearingTileId.value = cleared.removedId;
  await wait(CLEAR_ANIMATION_MS);
  tiles.value = cleared.tiles;
  clearingTileId.value = null;

  const penalty = calcClearPenalty(cleared.clearedValue, score.value);
  score.value = applyScorePenalty(score.value, penalty);
  scorePenalty.value += penalty;
  clearCellUses.value += 1;
  usedClearCell.value += 1;
  activeTool.value = '';
  recordPropUsage(GAME2048_PROP.CLEAR_CELL, `清除 ${cleared.clearedValue}`);
  isMoving.value = false;
  gameMessage.value = `清除锤已使用，扣除 ${penalty} 分`;

  if (isGameOverTiles(tiles.value)) {
    await settleGame(true);
  }
}

/**
 * 开始或重新开始一局。
 */
async function startOrRestartGame() {
  if (!canStartOrRestartGame.value) {
    showToast('请等待当前操作完成', 'warning');
    return;
  }
  const wasIdle = gameStatus.value === 'idle';
  moveGeneration++;
  resultModal.visible = false;
  setupBoard(
    wasIdle ? '对局已开始，滑动棋盘继续' : '已重新开始，滑动棋盘即可继续'
  );
  matchSessionId.value = session.newMatchSessionId();
  currentMatchPropUses.value = [];
  gameStatus.value = 'playing';
  startTimer();
  boardComponentRef.value?.focusBoard?.();
}

/**
 * 主动结束对局。
 */
async function endCurrentGame() {
  if (gameStatus.value === 'idle') {
    showToast('尚未开始对局', 'info');
    return;
  }
  if (gameStatus.value === 'ended' || gameStatus.value === 'settling') {
    return;
  }
  if (isOperationLocked.value) {
    showToast('请等待当前操作完成', 'warning');
    return;
  }
  await settleGame(false);
}

/**
 * @param {boolean} naturalGameOver
 */
async function settleGame(naturalGameOver) {
  if (gameStatus.value === 'ended' || gameStatus.value === 'settling') {
    return;
  }
  moveGeneration++;
  ensureSession();
  isSettling.value = true;
  gameStatus.value = 'settling';
  stopTimer();
  activeTool.value = '';

  const payload = {
    maxTile: maxTile.value,
    moves: moves.value,
    reached2048: reached2048Flag.value,
    clearCellUses: clearCellUses.value,
    scorePenalty: scorePenalty.value
  };
  const reward = rewardForScore();

  try {
    await session.settleWin({
      score: score.value,
      rewardScore: reward,
      difficultyCode: difficultyCode.value,
      durationMs: Math.round(elapsedSec.value * 1000),
      propUses: currentMatchPropUses.value,
      sessionId: matchSessionId.value,
      mode: GAME2048_MODE,
      matchPayload: payload,
      scorePayload: payload
    });
  } finally {
    isSettling.value = false;
    isMoving.value = false;
  }

  gameStatus.value = 'ended';
  resultModal.visible = true;
  resultModal.score = score.value;
  resultModal.reward = reward;
  resultModal.moves = moves.value;
  resultModal.maxTile = maxTile.value;
  resultModal.reached2048 = reached2048Flag.value;
  resultModal.clearCellUses = clearCellUses.value;
  resultModal.scorePenalty = scorePenalty.value;
  resultModal.gameOver = naturalGameOver;
  gameMessage.value = naturalGameOver ? '无可移动方向，对局结束' : '对局已结束';
}

/**
 * 页面级键盘（仅在本游戏页挂载）。
 * @param {KeyboardEvent} event
 */
function onWindowKeydown(event) {
  if (moveInputLocked.value) {
    return;
  }
  const tag = event.target?.tagName?.toLowerCase?.() || '';
  if (tag === 'input' || tag === 'textarea' || tag === 'select') {
    return;
  }
  const key = event.key;
  if (
    key === 'ArrowUp' ||
    key === 'ArrowDown' ||
    key === 'ArrowLeft' ||
    key === 'ArrowRight' ||
    key === 'w' ||
    key === 'W' ||
    key === 'a' ||
    key === 'A' ||
    key === 's' ||
    key === 'S' ||
    key === 'd' ||
    key === 'D'
  ) {
    event.preventDefault();
    const map = {
      ArrowUp: 'up',
      ArrowDown: 'down',
      ArrowLeft: 'left',
      ArrowRight: 'right',
      w: 'up',
      W: 'up',
      s: 'down',
      S: 'down',
      a: 'left',
      A: 'left',
      d: 'right',
      D: 'right'
    };
    handleMoveInput(map[key]);
  }
}

onMounted(async () => {
  platform.setCurrentGame(GAME2048_CODE);
  await activateGame(GAME2048_CODE, {
    difficultyCode: difficultyCode.value,
    mode: GAME2048_MODE,
    includeInventory: true
  });
  setupBoard();
  window.addEventListener('keydown', onWindowKeydown);
  boardComponentRef.value?.focusBoard?.();
});

onBeforeUnmount(() => {
  stopTimer();
  window.removeEventListener('keydown', onWindowKeydown);
});
</script>
