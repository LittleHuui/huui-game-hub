import { computed } from 'vue';
import { GAME_ACTION_SIZE, GAME_ACTION_TYPE, GAME_CONTROL_TYPE, GAME_STAT_TONE } from '../../components/game/index.js';
import { sudokuGameModule } from './gameModule.js';
import { countConflictCells, countEmptyCells, countFilledCells } from './sudokuEngine.js';
import { SUDOKU_CODE, SUDOKU_PROP } from './sudokuConfig.js';
import { formatDurationMmSs } from '../../utils/timeService.js';
import { getDifficultyName, toDifficultySelectorOptions } from '../../services/gameDifficultyService.js';

/** 派生控制区、统计与结果展示，不执行对局规则。
 * @param {object} context
 * @returns {object}
 */
export function createSudokuPresentation(context) {
  const { canUseHint, difficultyCode, gameStatus, isPaused, propRemaining, propLimit, elapsedSec, cells, propQuantity, usedHintCount, gameMessage, canPlayAgain, canRestartGame, canEndGame, resultModal, playAgain, restartGame, pauseGame, resumeGame, endCurrentGame } = context;

  const displayMetadata = sudokuGameModule.displayMetadata;
  const difficultyOptions = computed(() => toDifficultySelectorOptions(SUDOKU_CODE));
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
  const layoutGameTitle = computed(() => displayMetadata.name);
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

  return {
    displayMetadata,
    difficultyOptions,
    inventoryDisabledProps,
    inventoryUseLabels,
    difficultyLabel,
    controlFields,
    matchQuotas,
    matchStats,
    statusLabel,
    matchStatsMessage,
    layoutGameTitle,
    layoutGameDescription,
    layoutGameStatusText,
    actionItems,
    openResultModal,
    openResultModalEnd,
    onLayoutAction,
    onResultModalAction
  };
}
