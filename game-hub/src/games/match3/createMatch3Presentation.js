import { formatDurationMmSs } from '../../utils/timeService.js';
import { computed } from 'vue';
import { GAME_ACTION_SIZE, GAME_ACTION_TYPE, GAME_CONTROL_TYPE, GAME_STAT_TONE } from '../../components/game/index.js';
import { match3GameModule } from './gameModule.js';
import { MATCH3_PROP } from './match3Config.js';
import { getDifficultyName } from '../../services/gameDifficultyService.js';

/** 派生控制区、统计与结果展示，不执行对局规则。
 * @param {object} context
 * @returns {object}
 */
export function createMatch3Presentation(context) {
  const { MATCH3, difficultyCode, mode, isPaused, gameStatus, canUseProps, propQuantity, propRemaining, activeTool, propLimit, isGameInProgress, animating, boardResolving, canPauseGame, canRestartGame, canEndGame, score, remainingSec, elapsedSec, moves, comboMax, changeMode, playAgain, restartGame, pauseGame, resumeGame, endCurrentGame, usedProps, resultModal } = context;

  const displayMetadata = match3GameModule.displayMetadata;
  const layoutGameTitle = computed(() => displayMetadata.name);
  const layoutGameDescription = computed(() => {
    const diffName = getDifficultyName(MATCH3, difficultyCode.value);
    return mode.value === 'timed' ? `限时模式 · ${diffName}` : `无限模式 · ${diffName}`;
  });
  const layoutGameStatusText = computed(() => {
    if (isPaused.value && gameStatus.value === 'playing') {
      return '对局已暂停';
    }
    const map = {
      idle: '尚未开始对局',
      playing: '对局进行中',
      ended: '对局已结束'
    };
    return map[gameStatus.value] || '';
  });
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
  const matchQuotas = computed(() => [
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
  const controlFields = computed(() => [
    {
      key: 'mode',
      label: '模式',
      type: GAME_CONTROL_TYPE.RADIO,
      value: mode.value,
      options: [
        { label: '限时', value: 'timed' },
        { label: '无限', value: 'endless' }
      ],
      disabled: isGameInProgress.value
    }
  ]);
  const actionItems = computed(() => {
    const items = [];
    const status = gameStatus.value;
    const ended = status === 'ended';
    const playing = status === 'playing';
    const paused = playing && isPaused.value;
    const settling = animating.value || boardResolving.value;

    if (ended) {
      items.push({
        key: 'playAgain',
        label: '再来一局',
        type: GAME_ACTION_TYPE.PRIMARY,
        size: GAME_ACTION_SIZE.MD,
        visible: true,
        disabled: settling
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
        disabled: !canPauseGame.value || settling
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

    if (playing || paused) {
      items.push({
        key: 'restart',
        label: '重新开始',
        type: GAME_ACTION_TYPE.SECONDARY,
        size: GAME_ACTION_SIZE.MD,
        visible: true,
        disabled: !canRestartGame.value || settling
      });
      items.push({
        key: 'end',
        label: '结束对局',
        type: GAME_ACTION_TYPE.DANGER,
        size: GAME_ACTION_SIZE.MD,
        visible: true,
        disabled: !canEndGame.value || settling
      });
    }

    return items;
  });
  const matchStats = computed(() => {
    const timed = mode.value === 'timed';
    return [
      {
        key: 'score',
        label: '得分',
        value: score.value,
        tone: GAME_STAT_TONE.ACCENT,
        icon: '★'
      },
      {
        key: 'time',
        label: timed ? '剩余' : '用时',
        value: timed ? `${remainingSec.value}s` : formatDurationMmSs(elapsedSec.value),
        helper: timed ? '倒计时' : '累计',
        icon: '⏱'
      },
      {
        key: 'moves',
        label: '步数',
        value: moves.value,
        icon: '↔'
      },
      {
        key: 'comboMax',
        label: '最大连击',
        value: comboMax.value,
        icon: '⚡'
      },
      {
        key: 'mode',
        label: '模式',
        value: timed ? '限时' : '无限',
        tone: GAME_STAT_TONE.MUTED
      }
    ];
  });

  /**
   * 左侧配置项变更（模式切换）。
   * @param {{ key: string; value: unknown }} payload
   */
  function onControlFieldChange(payload) {
    if (payload.key === 'mode' && payload.value !== mode.value) {
      changeMode(payload.value);
    }
  }

  /**
   * 轻量单人模板操作按钮回调。
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
      endCurrentGame();
    }
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
      playAgain();
      return;
    }
    if (actionKey === 'close') {
      resultModal.visible = false;
    }
  }

  return {
    displayMetadata,
    layoutGameTitle,
    layoutGameDescription,
    layoutGameStatusText,
    rankingSubtitle,
    inventoryDisabledProps,
    inventoryUseLabels,
    matchQuotas,
    controlFields,
    actionItems,
    matchStats,
    onControlFieldChange,
    onLayoutAction,
    openResultModal,
    onResultModalAction
  };
}
