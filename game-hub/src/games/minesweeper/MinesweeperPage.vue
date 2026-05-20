<template>
  <div>
    <GamePlayLayout>
      <template #config>
        <GameConfigPanel title="游戏信息">
          <template #title-extra>
            <div class="info-tip-wrap" tabindex="0">
              <button type="button" class="info-tip-btn" aria-label="积分规则说明">!</button>
              <div class="info-tip-bubble" role="tooltip">
                积分规则：胜利直接获得当前难度满积分（初级100 / 中级300 / 高级800）；失败或主动结束时，按正确标记雷数 × 3 结算。
              </div>
            </div>
          </template>
          <MinesweeperHud
          :difficulty-label="difficultyLabel"
          :difficulty-open="difficultyOpen"
          :is-game-in-progress="isGameInProgress"
          :paused="paused"
          :can-use-safe-start-hint="canUseSafeStartHint"
          :difficulty="difficulty"
          :difficulty-options="difficultyOptions"
          @toggle-difficulty-menu="toggleDifficultyMenu"
          @select-difficulty="selectDifficulty"
          @toggle-pause="togglePause"
          @start-or-restart="startOrRestartGame"
          @safe-start="safeStartHint"
          @end-game="endCurrentGame"
          />
        </GameConfigPanel>
      </template>

      <template #shop>
        <GameShopPanel game-code="minesweeper" :session-id="matchSessionId" />
      </template>

      <template #ranking>
        <GameRankingPanel
          game-code="minesweeper"
          mode="single"
          :difficulty-code="difficulty"
          value-metric="durationMs"
          :subtitle="`${difficultyLabel} · 全服前十名（按用时排序）`"
        />
      </template>

      <template #hud>
        <GameHudPanel>
          <GameHudStats :theme-seed="statThemeSeed">
            <GameStatGrid compact :columns="3" min-column-width="84px">
              <GameStatCard
                label="积分"
                :value="user.score || 0"
                tone="accent"
                icon="★"
                layout="inline"
              />
              <GameStatCard label="剩余雷" :value="remainMines" icon="💣" layout="inline" />
              <GameStatCard label="用时" :value="`${timer}s`" icon="⏱" layout="inline" />
            </GameStatGrid>
            <GameStatQuotaBar :items="statQuotaItems" />
            <p v-if="gameMessage" class="game-hud-stats__message">{{ gameMessage }}</p>
          </GameHudStats>
        </GameHudPanel>
      </template>

      <template #board>
        <MinesweeperBattlePanel
          :board="board"
          :rows="rows"
          :cols="cols"
          :window-width="windowWidth"
          :neighbor-ring-keys="neighborRingKeys"
          :paused="paused"
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
          game-code="minesweeper"
          :usable-props="[MINESWEEPER_PROP.HINT]"
          :active-prop="activeTool === 'hint' ? MINESWEEPER_PROP.HINT : ''"
          :disabled-props="inventoryDisabledProps"
          :use-labels="inventoryUseLabels"
          @use-prop="onInventoryUseProp"
        >
          <template #footer>
            <label class="backpack-revive-inline" title="有卡且本局未复活时，踩雷自动消耗一张">
              <input type="checkbox" :checked="!!user.autoRevive" @change="setAutoRevive($event.target.checked)" />
              <span>复活卡自动使用</span>
            </label>
          </template>
        </GameInventoryPanel>
      </template>
    </GamePlayLayout>

    <MinesweeperReviveModal
      :visible="reviveOffer.visible"
      :seconds-left="reviveOffer.secondsLeft"
      :revive-disabled="reviveQty <= 0"
      @confirm="confirmReviveOffer"
      @decline="declineReviveOffer"
    />
  </div>
</template>

<script setup>
import './minesweeper.css';
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import MinesweeperHud from './components/MinesweeperHud.vue';
import MinesweeperReviveModal from './components/MinesweeperReviveModal.vue';
import MinesweeperBattlePanel from './components/MinesweeperBattlePanel.vue';
import GamePlayLayout from '../../components/game/GamePlayLayout.vue';
import GameConfigPanel from '../../components/game/GameConfigPanel.vue';
import GameShopPanel from '../../components/game/GameShopPanel.vue';
import GameRankingPanel from '../../components/game/GameRankingPanel.vue';
import GameHudPanel from '../../components/game/GameHudPanel.vue';
import GameHudStats from '../../components/game/GameHudStats.vue';
import GameStatCard from '../../components/game/GameStatCard.vue';
import GameStatGrid from '../../components/game/GameStatGrid.vue';
import GameStatQuotaBar from '../../components/game/GameStatQuotaBar.vue';
import GameInventoryPanel from '../../components/game/GameInventoryPanel.vue';
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

/** 统计区配色：0–9 | 主题名（如 emerald）| random */
const statThemeSeed = 'random';
const session = createGameSession({ gameCode: MINESWEEPER_GAME_CODE });
const user = session.currentUser;
const propQuantities = useGamePropQuantities(MINESWEEPER_GAME_CODE);

/**
 * @param {string} propCode
 * @returns {number}
 */
function propQty(propCode) {
  return propQuantities.value[propCode] || 0;
}

const hintQty = computed(() => propQty(MINESWEEPER_PROP.HINT));
const reviveQty = computed(() => propQty(MINESWEEPER_PROP.REVIVE));
const difficultyOpen = ref(false);
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
const paused = ref(false);
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
const canUseBattleProps = computed(() => isGameInProgress.value && !paused.value && !reviveOffer.visible);
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
const hintExhausted = computed(
  () => hintQty.value <= 0 || usedHintCount.value >= hintMatchLimit.value
);
const canUseSafeStartHint = computed(() => !isGameInProgress.value);
const difficultyLabel = computed(() => getDifficultyName(MINESWEEPER_GAME_CODE, difficulty.value));

const statQuotaItems = computed(() => [
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

const inventoryDisabledProps = computed(() => ({
  [MINESWEEPER_PROP.HINT]: !canUseBattleProps.value || hintBackpackExhausted.value
}));

const inventoryUseLabels = computed(() => ({
  [MINESWEEPER_PROP.HINT]: activeTool.value === 'hint' ? '选格' : '用'
}));

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
    timer.value++;
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
  difficultyOpen.value = false;
  timer.value = 0;
  gameStarted.value = false;
  gameOver.value = false;
  gameWin.value = false;
  boardShake.value = false;
  usedHintCount.value = 0;
  revived.value = false;
  activeTool.value = '';
  paused.value = false;
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

function startOrRestartGame() {
  startGame();
  ensureSession();
  gameStarted.value = true;
  startTimer();
}

function toggleDifficultyMenu() {
  if (isGameInProgress.value) {
    showToast('对局进行中，无法切换难度', 'warning');
    return;
  }
  difficultyOpen.value = !difficultyOpen.value;
}

function selectDifficulty(value) {
  if (isGameInProgress.value) {
    showToast('对局进行中，无法切换难度', 'warning');
    return;
  }
  if (!isDifficultyEnabled(MINESWEEPER_GAME_CODE, value)) {
    showToast('该难度不可用', 'warning');
    return;
  }
  difficulty.value = value;
  difficultyOpen.value = false;
  if (!isGameInProgress.value) {
    startGame();
  }
}

function togglePause() {
  if (gameOver.value) {
    return;
  }
  paused.value = !paused.value;
  if (paused.value) {
    stopTimer();
    gameMessage.value = '游戏已暂停';
  } else if (gameStarted.value) {
    startTimer();
    gameMessage.value = '游戏继续';
  }
}

function rightClick(cell) {
  if (gameOver.value || paused.value || reviveOffer.visible) {
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
  if (gameOver.value || paused.value || reviveOffer.visible) {
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

async function endCurrentGame() {
  if (!isGameInProgress.value) {
    return;
  }
  stopTimer();
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
  startGame(`已结束对局，获得 ${endScore} 积分`);
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
  gameMessage.value = `游戏失败，获得 ${failScore} 积分`;
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
}

async function winGame() {
  gameOver.value = true;
  gameWin.value = true;
  stopTimer();
  const correctFlags = Svc.countCorrectFlags(board.value, rows.value, cols.value);
  const score = MINESWEEPER_PRESETS[difficulty.value].scoreWin;
  await session.settleWin({
    score,
    difficultyCode: difficulty.value,
    durationMs: Math.round(timer.value * 1000),
    mode: MINESWEEPER_MODE,
    propUses: currentMatchPropUses.value,
    sessionId: matchSessionId.value
  });
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

function pauseDueToPageHidden() {
  if (!isGameInProgress.value || paused.value) {
    return;
  }
  paused.value = true;
  stopTimer();
  gameMessage.value = '已离开当前页面，游戏已自动暂停。返回后请点击「继续游戏」。';
}

onMounted(async () => {
  await activateGame(MINESWEEPER_GAME_CODE, {
    mode: MINESWEEPER_MODE,
    difficultyCode: difficulty.value,
    includeInventory: true
  });
  startGame('开始你的扫雷挑战吧');
  document.addEventListener('visibilitychange', pauseDueToPageHidden);
  window.addEventListener('resize', handleResize);
  handleResize();
});

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', pauseDueToPageHidden);
  window.removeEventListener('resize', handleResize);
  stopTimer();
  stopReviveOfferTimer();
});
</script>
