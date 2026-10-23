import { computed } from 'vue';
import {
  GAME_ACTION_SIZE,
  GAME_ACTION_TYPE,
  GAME_STAT_TONE
} from '../../components/game/index.js';
import { GAME2048_PROP } from './game2048Config.js';

/**
 * Creates presentational computed values for the 2048 page shell.
 * @param {{ state: object, displayMetadata: object, rewardScorePreview: import('vue').ComputedRef<number>, formatDurationMmSs: Function }} deps
 * @returns {object}
 */
export function use2048Presentation({
  state,
  displayMetadata,
  rewardScorePreview,
  formatDurationMmSs
}) {
  const inventoryDisabledProps = computed(() => ({
    [GAME2048_PROP.CLEAR_CELL]:
      !state.canUseClearCell.value || state.propQuantity(GAME2048_PROP.CLEAR_CELL) <= 0
  }));
  const inventoryUseLabels = computed(() => ({
    [GAME2048_PROP.CLEAR_CELL]:
      state.activeTool.value === GAME2048_PROP.CLEAR_CELL ? '取消' : '使用'
  }));
  const controlFields = computed(() => []);
  const matchQuotas = computed(() => [
    {
      label: '清除锤',
      used: state.propRemaining(GAME2048_PROP.CLEAR_CELL),
      max: state.propLimit(GAME2048_PROP.CLEAR_CELL)
    }
  ]);
  const matchStats = computed(() => [
    { key: 'score', label: '当前分数', value: state.score.value, tone: GAME_STAT_TONE.ACCENT },
    { key: 'maxTile', label: '最大数字', value: state.maxTile.value },
    { key: 'moves', label: '移动次数', value: state.moves.value },
    { key: 'duration', label: '用时', value: formatDurationMmSs(state.elapsedSec.value) },
    { key: 'clearUses', label: '清除锤使用次数', value: state.clearCellUses.value },
    { key: 'penalty', label: '扣除分数', value: state.scorePenalty.value, tone: GAME_STAT_TONE.MUTED },
    { key: 'reward', label: '预计平台积分', value: rewardScorePreview.value, helper: '预计' }
  ]);
  const matchStatsMessage = computed(() =>
    state.reached2048Flag.value
      ? state.gameMessage.value
        ? `已达成 2048 · ${state.gameMessage.value}`
        : '已达成 2048'
      : state.gameMessage.value
  );
  const layoutGameTitle = computed(() => displayMetadata.name);
  const layoutGameDescription = computed(() => '经典模式 · 标准难度');
  const layoutGameStatusText = computed(() => {
    if (state.isPaused.value && state.gameStatus.value === 'playing') {
      return '对局已暂停';
    }
    return {
      idle: '尚未开始对局',
      playing: '对局进行中',
      settling: '正在结算...',
      ended: '对局已结束'
    }[state.gameStatus.value] || '';
  });
  const actionItems = computed(() => buildActionItems(state));

  return {
    inventoryDisabledProps,
    inventoryUseLabels,
    controlFields,
    matchQuotas,
    matchStats,
    matchStatsMessage,
    layoutGameTitle,
    layoutGameDescription,
    layoutGameStatusText,
    actionItems
  };
}

/**
 * Builds the layout action bar items from 2048 runtime state.
 * @param {object} state
 * @returns {Array<object>}
 */
function buildActionItems(state) {
  const items = [];
  const status = state.gameStatus.value;
  const playing = status === 'playing';
  const paused = playing && state.isPaused.value;
  if (status === 'ended') {
    return [
      {
        key: 'playAgain',
        label: '再来一局',
        type: GAME_ACTION_TYPE.PRIMARY,
        size: GAME_ACTION_SIZE.MD,
        visible: true,
        disabled: !state.canPlayAgain.value
      }
    ];
  }
  if (status === 'idle') {
    return items;
  }
  if (playing && !state.isPaused.value) {
    items.push({
      key: 'pause',
      label: '暂停游戏',
      type: GAME_ACTION_TYPE.PAUSE,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: state.isOperationLocked.value
    });
  }
  if (paused) {
    items.push({
      key: 'resume',
      label: '继续游戏',
      type: GAME_ACTION_TYPE.RESUME,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: status === 'settling'
    });
  }
  if (playing || paused || status === 'settling') {
    items.push({
      key: 'restart',
      label: '重新开始',
      type: GAME_ACTION_TYPE.SECONDARY,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: !state.canRestartGame.value
    });
    items.push({
      key: 'end',
      label: '结束对局',
      type: GAME_ACTION_TYPE.DANGER,
      size: GAME_ACTION_SIZE.MD,
      visible: true,
      disabled: !state.canEndGame.value
    });
  }
  return items;
}
