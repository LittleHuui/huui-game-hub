import { formatDurationMmSs } from '../../utils/timeService.js';
import { computed } from 'vue';
import { GAME_ACTION_SIZE, GAME_ACTION_TYPE, GAME_CONTROL_TYPE, GAME_STAT_TONE } from '../../components/game/index.js';
import { minesweeperGameModule } from './gameModule.js';
import { MINESWEEPER_GAME_CODE, MINESWEEPER_PROP } from './minesweeperConfig.js';
import { getDifficultyName, toDifficultySelectorOptions } from '../../services/gameDifficultyService.js';

/** 派生控制区、统计与结果展示，不执行对局规则。
 * @param {object} context
 * @returns {object}
 */
export function createMinesweeperPresentation(context) {
  const { difficulty, gameOver, isGameInProgress, isPaused, canUseSafeStartHint, matchPropRemaining, hintMatchLimit, reviveMatchLimit, user, remainMines, timer, openedCount, flaggedCount, canUseBattleProps, hintBackpackExhausted, activeTool, changeDifficulty, pauseGame, resumeGame, restartGame, playAgain, safeStartHint, endCurrentGame, useHintCard, resultModal } = context;

  /** 统计区配色：0–9 | 主题名 | random */
  const statThemeSeed = 'random';

  const displayMetadata = minesweeperGameModule.displayMetadata;
  const difficultyOptions = computed(() => toDifficultySelectorOptions(MINESWEEPER_GAME_CODE));
  const difficultyLabel = computed(() => getDifficultyName(MINESWEEPER_GAME_CODE, difficulty.value));
  const layoutGameTitle = computed(() => displayMetadata.name);
  const layoutGameSubtitle = computed(() => displayMetadata.subName);
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
      label: '提示卡',
      used: matchPropRemaining(MINESWEEPER_PROP.HINT, hintMatchLimit.value),
      max: hintMatchLimit.value,
      themeSeed: 'amber'
    },
    {
      label: '复活卡',
      used: matchPropRemaining(MINESWEEPER_PROP.REVIVE, reviveMatchLimit),
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

  return {
    statThemeSeed,
    displayMetadata,
    difficultyOptions,
    difficultyLabel,
    layoutGameTitle,
    layoutGameSubtitle,
    layoutGameDescription,
    layoutGameStatusText,
    controlFields,
    actionItems,
    matchQuotas,
    matchStats,
    inventoryDisabledProps,
    inventoryUseLabels,
    handleControlChange,
    handleControlAction,
    onInventoryUseProp,
    openResultModal,
    onResultModalAction
  };
}
