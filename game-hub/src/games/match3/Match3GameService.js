import { buildMatch3Settlement } from './match3Settlement.js';
import { createMatch3Animation } from './createMatch3Animation.js';
import { createAnimationTimeline } from '../../composables/createAnimationTimeline.js';
import { createRoundCompletion } from './createRoundCompletion.js';
import { computed, reactive, ref } from 'vue';
import { applyBomb, canSwap, cloneBoard, createBoard, hasAvailableMove, shuffleBoard, swapCells } from './match3Engine.js';
import { getMatch3ClientConfig, getMatch3DifficultyConfig, getMatch3ModePropLimit, getMatch3PropRule, MATCH3_PROP } from './match3Config.js';
import { useGamePropQuantities } from '../../composables/useGamePropQuantities.js';
import { createGameSession } from '../../services/gameSessionService.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import * as toastService from '../../services/toastService.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import { getDefaultDifficultyCode } from '../../services/gameDifficultyService.js';
import { createGameTimer } from '../../composables/createGameTimer.js';

const SHUFFLE_ANIMATION_MS = 380;

/** 管理棋盘规则动作、对局状态和道具记录；页面模型由 useMatch3Page 组合。
 * @param {object} presentation
 * @returns {object}
 */
export function createMatch3Game({ resultModal, openResultModal }) {
  const MATCH3 = 'match3';
  const difficultyCode = computed(
    () => getMatch3DifficultyConfig().difficultyCode || getDefaultDifficultyCode(MATCH3)
  );

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

  const gameTimer = createGameTimer({
    onTick: () => {
      if (isPaused.value || isSettling.value || gameStatus.value !== 'playing') {
        return;
      }
      elapsedSec.value++;
      if (mode.value === 'timed') {
        remainingSec.value = Math.max(0, remainingSec.value - 1);
        if (remainingSec.value <= 0) {
          void settleGame(false);
        }
      }
    }
  });
  const isPaused = ref(false);

  /** 棋盘动画/结算中（交换、下落、连击、补满等） */
  const animating = ref(false);

  /** 连锁消除与计分结算中 */
  const boardResolving = ref(false);

  /** 结束对局或提交结算期间锁定操作 */
  const isSettling = ref(false);

  const animationTimeline = createAnimationTimeline();

  const { wait, nextFrame } = animationTimeline;

  const roundCompletion = createRoundCompletion({
    settle: finalizeGame,
    onEndingChanged: (value) => { isSettling.value = value; }
  });
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
    () =>
      !isSettling.value && !isPaused.value && (gameStatus.value === 'idle' || gameStatus.value === 'playing')
  );
  const inputLocked = computed(
    () => !canBoardInteract.value || animating.value || resultModal.visible
  );
  const canUseProps = computed(
    () => gameStatus.value === 'playing' && !isSettling.value && !isPaused.value && !animating.value
  );
  const canRestartGame = computed(() => !isSettling.value && !animating.value && !boardResolving.value);
  const canPauseGame = computed(
    () =>
      gameStatus.value === 'playing' &&
      !isSettling.value &&
      !animating.value &&
      !boardResolving.value &&
      !inputLocked.value
  );
  const canEndGame = computed(
    () => gameStatus.value === 'playing' && !animating.value && !boardResolving.value
  );

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
   * 停止计时
   */
  function stopTimer() {
    gameTimer.stop();
  }

  /**
   * 启动计时
   */
  function startTimer() {
    stopTimer();
    gameTimer.start();
  }

  /**
   * 暂停对局：停止计时并锁定新输入（不打断进行中的动画）。
   */
  function pauseGame() {
    if (gameStatus.value !== 'playing' || isPaused.value) {
      return;
    }
    if (!canPauseGame.value) {
      showToast('请等待当前动画完成', 'warning');
      return;
    }
    isPaused.value = true;
    activeTool.value = '';
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
    if (gameStatus.value === 'playing') {
      gameMessage.value = '对局已继续';
    }
  }

  /**
   * 重置运行时状态
   * @param {string} [message]
   */
  function resetRuntime(message) {
    animationTimeline.cancel();
    roundCompletion.reset();
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
    isPaused.value = false;
    gameMessage.value = message || '拖动方块交换即可开始';
  }

  /**
   * @returns {boolean}
   */
  function isResolutionStale(gen) {
    return gen !== roundCompletion.generation;
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
    isPaused.value = false;
    setupBoard('已重新生成棋盘，拖动方块交换即可开始');
  }

  /**
   * 已结束对局：再来一局（回到 idle，首次有效交换自动开局）。
   */
  function playAgain() {
    if (!canRestartGame.value) {
      showToast('棋盘结算中，请稍候', 'warning');
      return;
    }
    resultModal.visible = false;
    restartGame();
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
   * @param {{ from: { row: number; col: number }; to: { row: number; col: number } }} payload
   */
  async function handleSwapRequest(payload) {
    if (inputLocked.value) return;
    await performBoardAction(() => swapBoard(payload));
  }

  /**
   * 统一接纳交换与道具动作，并处理死盘、取消和操作失败。
   * @param {Function} action
   * @returns {Promise<void>}
   */
  async function performBoardAction(action) {
    const gen = roundCompletion.generation;
    try {
      const result = await roundCompletion.run(action);
      if (!result || result.aborted || isResolutionStale(gen)) return;
      if (result.deadBoard) await settleGame(true);
    } catch (error) {
      if (!isResolutionStale(gen)) showToast(error?.message || '棋盘操作失败，请重新开始', 'error');
    } finally {
      if (!isResolutionStale(gen)) animating.value = false;
    }
  }

  /** 执行一次交换及其完整连锁。 @param {object} payload @returns {Promise<object|undefined>} */
  async function swapBoard(payload) {
    if (inputLocked.value) {
      return;
    }
    const from = payload.from;
    const to = payload.to;
    if (from.row === to.row && from.col === to.col) {
      return;
    }

    const gen = roundCompletion.generation;
    animating.value = true;
    if (!canSwap(board.value, from, to)) {
      await playSwapAnimation(from, to, true);
      if (isResolutionStale(gen)) return;
      animating.value = false;
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
    gameMessage.value = result.comboCount > 0
      ? `+${result.scoreDelta} 分`
      : '继续拖动方块消除吧';
    return result;
  }

  /**
   * @param {object} cell
   */
  async function handleBombCellClick(cell) {
    if (inputLocked.value || activeTool.value !== 'bomb') {
      return;
    }
    await performBoardAction(() => applyBombProp(cell));
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
      await performBoardAction(applyShuffleProp);
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
    const gen = roundCompletion.generation;
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
    await wait(SHUFFLE_ANIMATION_MS);
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
    const gen = roundCompletion.generation;
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
    gameMessage.value = result.comboCount > 0
      ? `+${result.scoreDelta} 分`
      : '继续拖动方块消除吧';
    return result;
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
  function settleGame(deadBoard) {
    stopTimer();
    activeTool.value = '';
    return roundCompletion.finish(deadBoard).catch((error) => {
      showToast(error?.message || '对局结算失败，请重新开始', 'error');
      return null;
    });
  }

  /**
   * 将动作完成后的最终分数写入会话，并只向当前对局展示结果。
   * @param {boolean} deadBoard
   * @param {() => boolean} isCurrent
   * @returns {Promise<void>}
   */
  async function finalizeGame(deadBoard, isCurrent) {
    if (gameStatus.value === 'ended') {
      return;
    }
    ensureSession();
    gameStatus.value = 'ended';
    isPaused.value = false;
    stopTimer();
    const { reward, match } = buildMatch3Settlement({
      score: score.value,
      comboMax: comboMax.value,
      moves: moves.value,
      deadBoard,
      difficultyCode: difficultyCode.value,
      elapsedSec: elapsedSec.value,
      propUses: currentMatchPropUses.value,
      sessionId: matchSessionId.value,
      mode: mode.value
    }, gameConfig.value?.settlement || {});
    await session.settleWin(match);
    if (!isCurrent()) return;
    openResultModal(deadBoard, reward);
    gameMessage.value = deadBoard ? '棋盘无解，对局结束' : '对局已结束';
  }

  const { cellStride, hasEmptyCells, playSwapAnimation, playRemoveAnimation, playFallAnimation, playCollapseAndFill, animateBoardResolution } = createMatch3Animation({ clientConfig, CELL_GAP, board, animationConfig, cellVisuals, nextFrame, wait, roundCompletion, isResolutionStale, gameConfig, score, animating, boardResolving, chainHint, moves, comboMax });

  return {
    MATCH3,
    difficultyCode,
    CELL_GAP,
    session,
    platform,
    propQuantities,
    mode,
    board,
    activeTool,
    cellVisuals,
    chainHint,
    gameStatus,
    score,
    moves,
    comboMax,
    elapsedSec,
    remainingSec,
    gameMessage,
    matchSessionId,
    currentMatchPropUses,
    usedProps,
    gameTimer,
    isPaused,
    animating,
    boardResolving,
    isSettling,
    animationTimeline,
    wait,
    nextFrame,
    roundCompletion,
    gameConfig,
    clientConfig,
    animationConfig,
    isGameInProgress,
    canBoardInteract,
    inputLocked,
    canUseProps,
    canRestartGame,
    canPauseGame,
    canEndGame,
    showToast,
    ensureSession,
    modeTimeLimit,
    stopTimer,
    startTimer,
    pauseGame,
    resumeGame,
    resetRuntime,
    isResolutionStale,
    setupBoard,
    startMatchIfIdle,
    restartGame,
    playAgain,
    changeMode,
    handleSwapRequest,
    performBoardAction,
    swapBoard,
    handleBombCellClick,
    propLimit,
    propRemaining,
    propQuantity,
    recordPropUsage,
    useProp,
    applyShuffleProp,
    applyBombProp,
    endCurrentGame,
    settleGame,
    finalizeGame,
    cellStride,
    hasEmptyCells,
    playSwapAnimation,
    playRemoveAnimation,
    playFallAnimation,
    playCollapseAndFill,
    animateBoardResolution,
    MATCH3_PROP
  };
}
