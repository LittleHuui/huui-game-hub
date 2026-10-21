import { buildMinesweeperSettlement } from './minesweeperSettlement.js';
import { createAnimationTimeline } from '../../composables/createAnimationTimeline.js';
import { createMinesweeperInput } from './createMinesweeperInput.js';
import { ref, reactive, computed } from 'vue';
import * as Svc from './minesweeperEngine.js';
import { MINESWEEPER_GAME_CODE, MINESWEEPER_MODE, MINESWEEPER_PRESETS, MINESWEEPER_PROP, HINT_LIMIT_BY_DIFFICULTY } from './minesweeperConfig.js';
import { useGamePropQuantities } from '../../composables/useGamePropQuantities.js';
import { createGameSession } from '../../services/gameSessionService.js';
import { getDefaultDifficultyCode, isDifficultyEnabled } from '../../services/gameDifficultyService.js';
import * as toastService from '../../services/toastService.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import { createGameTimer } from '../../composables/createGameTimer.js';

const BOARD_SHAKE_MS = 500;

/** 管理棋盘规则动作、对局状态和道具记录；页面模型由 useMinesweeperPage 组合。
 * @param {object} presentation
 * @returns {object}
 */
export function createMinesweeperGame({ resultModal, openResultModal }) {
  let generation = 0;
  const animationTimeline = createAnimationTimeline();

  const session = createGameSession({ gameCode: MINESWEEPER_GAME_CODE });

  const platform = usePlatformStore();

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
  const difficulty = ref(getDefaultDifficultyCode(MINESWEEPER_GAME_CODE) || 'easy');

  /** 首帧渲染早于 onMounted，必须与 rows/cols 同步为完整棋盘，避免 flattenBoard 读 undefined */
  const initialPreset = MINESWEEPER_PRESETS[difficulty.value];
  const rows = ref(initialPreset.rows);
  const cols = ref(initialPreset.cols);
  const mines = ref(initialPreset.mines);
  const board = ref(Svc.createEmptyBoard(initialPreset.rows, initialPreset.cols));

  Svc.initBoard(board.value, initialPreset.rows, initialPreset.cols, initialPreset.mines);
  const timer = ref(0);

  const gameTimer = createGameTimer({
    onTick: () => {
      if (!isPaused.value && isGameInProgress.value) {
        timer.value++;
      }
    }
  });
  const gameStarted = ref(false);
  const gameOver = ref(false);
  const gameWin = ref(false);
  const boardShake = ref(false);
  const gameMessage = ref('开始你的扫雷挑战吧');
  const activeTool = ref('');
  const isPaused = ref(false);
  const safeHintUsed = ref(false);
  const revived = ref(false);
  const matchSessionId = ref(null);
  const currentMatchPropUses = ref([]);
  const reviveOffer = reactive({
    visible: false,
    cell: null,
    secondsLeft: 5,
    tickTimerId: null
  });
  const isGameInProgress = computed(() => gameStarted.value && !gameOver.value);
  const flatBoard = computed(() => Svc.flattenBoard(board.value, rows.value, cols.value));
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

  const reviveMatchLimit = 1;
  const hintMatchUsed = computed(() => matchPropUseCount(MINESWEEPER_PROP.HINT));
  const reviveMatchUsed = computed(() => matchPropUseCount(MINESWEEPER_PROP.REVIVE));
  const hintBackpackExhausted = computed(
    () => hintQty.value <= 0 || hintMatchUsed.value >= hintMatchLimit.value
  );
  const canUseSafeStartHint = computed(() => !isGameInProgress.value);

  /** 展示当前游戏操作反馈。 */
  function showToast(message, level = 'info', duration = 3200, toastKind = null) {
    toastService.push(message, level, duration, toastKind);
  }

  /**
   * 统计当前对局内指定道具的实际使用次数。
   * @param {string} propCode
   * @returns {number}
   */
  function matchPropUseCount(propCode) {
    return currentMatchPropUses.value.filter(
      (row) => row?.propCode === propCode || row?.type === propCode
    ).length;
  }

  /**
   * 本局道具剩余可用次数（非背包库存）。
   * @param {string} propCode
   * @param {number} limit
   * @returns {number}
   */
  function matchPropRemaining(propCode, limit) {
    return Math.max(0, limit - matchPropUseCount(propCode));
  }

  /** 首次操作时建立对局标识。 */
  function ensureSession() {
    if (!matchSessionId.value) {
      matchSessionId.value = session.newMatchSessionId();
      currentMatchPropUses.value = [];
    }
  }

  /** 停止等待复活选择的倒计时。 */
  function stopReviveOfferTimer() {
    if (reviveOffer.tickTimerId) {
      clearInterval(reviveOffer.tickTimerId);
      reviveOffer.tickTimerId = null;
    }
  }

  /** 记录当前对局道具消耗。 */
  function recordPropUsage(propCode, label) {
    ensureSession();
    session.trackPropUsage(currentMatchPropUses.value, {
      propCode,
      label,
      timerSec: timer.value,
      sessionId: matchSessionId.value
    });
  }

  /** 从当前用时继续计时，避免重复注册。 */
  function startTimer() {
    stopTimer();
    gameTimer.start();
  }

  /** 停止本局计时。 */
  function stopTimer() {
    gameTimer.stop();
  }

  /** 取消上一局异步展示并重置当前对局事实。 */
  function resetMatchRuntimeState(message) {
    generation++;
    animationTimeline.cancel();
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
    revived.value = false;
    activeTool.value = '';
    isPaused.value = false;
    safeHintUsed.value = false;
    gameMessage.value = message || '游戏开始';
  }

  /** 按当前难度生成棋盘并重置对局。 */
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

  /** 重新建立棋盘并启动新一局。 */
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

  /** 在可交互棋盘上循环格子标记。 */
  function rightClick(cell) {
    if (gameOver.value || isPaused.value || reviveOffer.visible) {
      return;
    }
    Svc.cycleFlag(cell);
  }

  /** 处理翻格、道具提示、踩雷与胜利判定。 */
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

  /** 安全翻开非雷格并开始计时。 */
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

  /** 主动结束当前进行中的对局。 */
  async function endCurrentGame() {
    if (!isGameInProgress.value) {
      return;
    }
    isPaused.value = false;
    stopTimer();
    gameOver.value = true;
    const current = generation;
    const match = buildMinesweeperSettlement('end', settlementState());
    const endScore = match.score;
    await session.settleEnd(match);
    if (current !== generation) return;
    openResultModal('end', endScore);
    gameMessage.value = `已结束对局，获得 ${endScore} 积分`;
  }

  /** 结束失败对局并在持久化后展示雷区和结算。 */
  async function failGame() {
    if (gameOver.value) return;
    stopReviveOfferTimer();
    reviveOffer.visible = false;
    reviveOffer.cell = null;
    gameOver.value = true;
    stopTimer();
    boardShake.value = true;
    const current = generation;
    const match = buildMinesweeperSettlement('fail', settlementState());
    const failScore = match.score;
    await session.settleFail(match);
    if (current !== generation) return;
    flatBoard.value.forEach((v) => {
      if (v && v.isMine) {
        v.opened = true;
      }
    });
    void animationTimeline.wait(BOARD_SHAKE_MS).then((completed) => {
      if (completed && current === generation) boardShake.value = false;
    });
    openResultModal('fail', failScore);
    gameMessage.value = `游戏失败，获得 ${failScore} 积分`;
  }

  /** 结束胜利对局并持久化成绩。 */
  async function winGame() {
    if (gameOver.value) return;
    gameOver.value = true;
    gameWin.value = true;
    stopTimer();
    const current = generation;
    const match = buildMinesweeperSettlement('win', settlementState());
    const score = match.score;
    await session.settleWin(match);
    if (current !== generation) return;
    openResultModal('win', score);
    gameMessage.value = `胜利！获得 ${score} 积分`;
    showToast('恭喜胜利', 'success');
  }

  /** 等待用户在倒计时内选择是否复活。 */
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

  /** 消费复活机会并继续对局。 */
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

  /** 关闭复活选择并按失败结算。 */
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

  /** 记录复活卡消耗并标记踩中的雷格。 */
  async function applyReviveFromMine(cell) {
    revived.value = true;
    recordPropUsage(MINESWEEPER_PROP.REVIVE, '复活卡：踩中格已标雷旗');
    cell.flagged = true;
    gameMessage.value = '复活卡已触发';
    showToast('已使用复活卡', 'success');
    session.persistLocal();
  }

  /** 进入提示卡选格状态。 */
  function useHintCard() {
    if (!canUseBattleProps.value) {
      showToast('对局未开始、已结束或已暂停时不可使用道具', 'warning');
      return;
    }
    if (hintQty.value <= 0) {
      showToast('没有提示卡', 'warning');
      return;
    }
    if (hintMatchUsed.value >= hintMatchLimit.value) {
      showToast('本局提示次数已达上限', 'warning');
      return;
    }
    activeTool.value = 'hint';
    gameMessage.value = '请选择一个格子进行提示';
  }

  /** 消费提示卡并显示目标格的雷状态。 */
  async function handleHint(cell) {
    if (cell.opened) {
      return;
    }
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

  /** 保存自动复活偏好并提示用户。 */
  async function setAutoRevive(value) {
    await session.setAutoRevive(value);
    showToast(value ? '已开启踩雷自动复活' : '已关闭踩雷自动复活', 'info');
  }

  const { windowWidth, neighborRingKeys, highlightAroundCells, clearNeighborRing, applyNeighborRingKeysFromCenter, onNeighborRingCellEnter, onNeighborRingCellLeave, handleResize } = createMinesweeperInput({ rows, cols });

  /** 读取一次结算所需的对局事实。 @returns {object} */
  function settlementState() {
    return {
      board: board.value, rows: rows.value, cols: cols.value, elapsedSec: timer.value,
      difficultyCode: difficulty.value, propUses: currentMatchPropUses.value, sessionId: matchSessionId.value
    };
  }

  /** 取消页面计时、复活倒计时和动画，并使旧结算展示失效。 @returns {void} */
  function dispose() {
    generation++;
    animationTimeline.cancel();
    stopTimer();
    stopReviveOfferTimer();
  }

  return {
    dispose,
    session,
    platform,
    user,
    propQuantities,
    propQty,
    hintQty,
    reviveQty,
    difficulty,
    initialPreset,
    rows,
    cols,
    mines,
    board,
    timer,
    gameTimer,
    gameStarted,
    gameOver,
    gameWin,
    boardShake,
    gameMessage,
    activeTool,
    isPaused,
    safeHintUsed,
    revived,
    matchSessionId,
    currentMatchPropUses,
    reviveOffer,
    isGameInProgress,
    flatBoard,
    remainMines,
    openedCount,
    flaggedCount,
    canUseBattleProps,
    hintMatchLimit,
    reviveMatchLimit,
    hintMatchUsed,
    reviveMatchUsed,
    hintBackpackExhausted,
    canUseSafeStartHint,
    showToast,
    matchPropUseCount,
    matchPropRemaining,
    ensureSession,
    stopReviveOfferTimer,
    recordPropUsage,
    startTimer,
    stopTimer,
    resetMatchRuntimeState,
    startGame,
    restartGame,
    playAgain,
    changeDifficulty,
    pauseGame,
    resumeGame,
    rightClick,
    clickCell,
    safeStartHint,
    endCurrentGame,
    failGame,
    winGame,
    startReviveOffer,
    confirmReviveOffer,
    declineReviveOffer,
    applyReviveFromMine,
    useHintCard,
    handleHint,
    setAutoRevive,
    windowWidth,
    neighborRingKeys,
    highlightAroundCells,
    clearNeighborRing,
    applyNeighborRingKeysFromCenter,
    onNeighborRingCellEnter,
    onNeighborRingCellLeave,
    handleResize,
    MINESWEEPER_GAME_CODE,
    MINESWEEPER_MODE,
    MINESWEEPER_PROP
  };
}
