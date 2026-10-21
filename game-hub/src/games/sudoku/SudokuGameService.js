import { buildSudokuSettlement } from './sudokuSettlement.js';
import { computed, ref } from 'vue';
import { computeRemainingCounts, findFirstEmptyEditableCell, getAvailableNumbers, isCellEditable, isPuzzleComplete, eraseCell, refreshCellConflicts, setCellValue, toggleDraft } from './sudokuEngine.js';
import { SUDOKU_CODE, SUDOKU_MODE, SUDOKU_PROP, getSudokuModePropLimit, getSudokuPropRule } from './sudokuConfig.js';
import { createBoardForDifficulty, isFilterUnavailableNumbersEnabled } from './sudokuService.js';
import { useGamePropQuantities } from '../../composables/useGamePropQuantities.js';
import { createGameSession } from '../../services/gameSessionService.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import { getDefaultDifficultyCode, isDifficultyEnabled } from '../../services/gameDifficultyService.js';
import * as toastService from '../../services/toastService.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import { createGameTimer } from '../../composables/createGameTimer.js';

/** 管理棋盘规则动作、对局状态和道具记录；页面模型由 useSudokuPage 组合。
 * @param {object} presentation
 * @returns {object}
 */
export function createSudokuGame({ resultModal, openResultModal, openResultModalEnd, closePopup, openPopupForCell }) {
  let generation = 0;

  const session = createGameSession({ gameCode: SUDOKU_CODE });

  const platform = usePlatformStore();

  const propQuantities = useGamePropQuantities(SUDOKU_CODE);
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
  const gameMessage = ref('点击空格或填数即可开始对局');
  const matchSessionId = ref(null);
  const currentMatchPropUses = ref([]);
  const usedHintCount = ref(0);
  const hintMatchLimit = ref(5);

  const gameTimer = createGameTimer({
    onTick: () => {
      if (!isPaused.value && gameStatus.value === 'playing') {
        elapsedSec.value++;
      }
    }
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

  /**
   * @param {string} message
   * @param {string} [level]
   */
  function showToast(message, level = 'info') {
    toastService.push(message, level);
  }

  /** 停止本局计时。 */
  function stopTimer() {
    gameTimer.stop();
  }

  /** 从当前用时继续计时，避免重复注册。 */
  function startTimer() {
    stopTimer();
    gameTimer.start();
  }

  /** 首次操作时建立对局标识。 */
  function ensureSession() {
    if (!matchSessionId.value) {
      matchSessionId.value = session.newMatchSessionId();
    }
  }

  /**
   * @param {string} [message]
   */
  function setupBoard(message) {
    generation++;
    const { cells: nextCells } = createBoardForDifficulty(difficultyCode.value);
    cells.value = nextCells;
    selectedRow.value = -1;
    selectedCol.value = -1;
    closePopup();
    gameMessage.value = message || '点击空格或填数即可开始对局';
  }

  /** 清除本局临时状态并建立待开始棋盘。 */
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

  /** 首次有效操作时启动对局和计时。 */
  function startMatchIfIdle() {
    if (gameStatus.value !== 'idle') {
      return;
    }
    ensureSession();
    gameStatus.value = 'playing';
    startTimer();
    gameMessage.value = '对局已开始，继续填数完成数独';
  }

  /** 暂停本局输入与计时推进。 */
  function pauseGame() {
    if (gameStatus.value !== 'playing' || isPaused.value) {
      return;
    }
    isPaused.value = true;
    closePopup();
    gameMessage.value = '游戏已暂停';
  }

  /** 恢复已暂停对局。 */
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

  /** 根据完整棋盘判定完成，否则继续当前对局。 */
  function afterBoardChange() {
    if (isPuzzleComplete(cells.value)) {
      void settleWin();
      return;
    }
    gameMessage.value = '继续填数完成数独';
  }

  /** 检查本局及背包限制并向空格填入唯一答案。 */
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

  /** 锁定完成状态，持久化本局成绩并展示结算。 */
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
    const current = generation;
    const { durationMs, reward, match } = buildSudokuSettlement('win', settlementState());
    try {
      await session.settleWin(match);
    } finally {
      if (current === generation) isSettling.value = false;
    }
    if (current !== generation) return;
    gameStatus.value = 'ended';
    openResultModal(durationMs, reward);
    gameMessage.value = '恭喜完成数独！';
  }

  /** 锁定主动结束状态，持久化当前成绩并展示结算。 */
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
    const current = generation;
    const { durationMs, reward: endScore, match } = buildSudokuSettlement('end', settlementState());
    try {
      await session.settleEnd(match);
    } finally {
      if (current === generation) isSettling.value = false;
    }
    if (current !== generation) return;
    gameStatus.value = 'ended';
    openResultModalEnd(durationMs, endScore);
    gameMessage.value = '对局已结束';
  }

  /** 重新建立棋盘并启动新一局。 */
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

  /** 关闭结算并回到首次操作开局状态。 */
  function playAgain() {
    if (!canPlayAgain.value) {
      return;
    }
    resultModal.visible = false;
    resetRuntime('点击空格或填数开始新对局');
  }

  /** 主动结束当前进行中的对局。 */
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

  /** 读取一次结算所需的对局事实。 @returns {object} */
  function settlementState() {
    return {
      cells: cells.value, elapsedSec: elapsedSec.value, difficultyCode: difficultyCode.value,
      propUses: currentMatchPropUses.value, sessionId: matchSessionId.value, hintUses: usedHintCount.value
    };
  }

  /** 结束页面计时并使未完成结算的展示回调失效。 @returns {void} */
  function dispose() {
    generation++;
    stopTimer();
  }

  return {
    dispose,
    session,
    platform,
    propQuantities,
    difficultyCode,
    cells,
    gameStatus,
    elapsedSec,
    isPaused,
    isSettling,
    draftMode,
    filterUnavailableNumbers,
    selectedRow,
    selectedCol,
    gameMessage,
    matchSessionId,
    currentMatchPropUses,
    usedHintCount,
    hintMatchLimit,
    gameTimer,
    propQuantity,
    propLimit,
    propRemaining,
    remainingCounts,
    popupAvailableNumbers,
    canInteractBoard,
    canEditBoard,
    canRestartGame,
    canPlayAgain,
    canEndGame,
    canUseHint,
    showToast,
    stopTimer,
    startTimer,
    ensureSession,
    setupBoard,
    resetRuntime,
    startMatchIfIdle,
    pauseGame,
    resumeGame,
    onSelectCell,
    onEraseCell,
    onPickNumber,
    afterBoardChange,
    useHintProp,
    settleWin,
    settleEnd,
    restartGame,
    playAgain,
    endCurrentGame,
    onControlFieldChange,
    SUDOKU_CODE,
    SUDOKU_MODE,
    SUDOKU_PROP
  };
}
