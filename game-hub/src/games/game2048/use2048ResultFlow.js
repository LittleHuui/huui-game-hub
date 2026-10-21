import { formatDurationMmSs } from '../../utils/timeService.js';
import { reactive } from 'vue';

/**
 * Creates the 2048 result modal and settlement flow.
 * @param {{ state: object, gameService: object, getPayload: Function }} deps
 * @returns {object}
 */
export function use2048ResultFlow({ state, gameService, getPayload }) {
  const resultModal = reactive({
    visible: false,
    title: '本局结算',
    subtitle: '',
    resultType: 'neutral',
    stats: [],
    rewards: [],
    highlights: [],
    actions: []
  });

  /**
   * Opens the result modal with the current match statistics.
   * @param {boolean} naturalGameOver
   * @param {number} reward
   * @returns {void}
   */
  function openResultModal(naturalGameOver, reward) {
    const reached = state.reached2048Flag.value;
    const highlights = [
      { label: '达成 2048', value: reached ? '是' : '否' },
      { label: '清除锤使用次数', value: state.clearCellUses.value }
    ];
    if (state.scorePenalty.value > 0) {
      highlights.push({ label: '清除锤扣分', value: state.scorePenalty.value });
    }
    Object.assign(resultModal, {
      visible: true,
      title: '本局结算',
      subtitle: naturalGameOver ? '无可移动方向，对局结束' : '对局已结束',
      resultType: reached ? 'success' : naturalGameOver ? 'failed' : 'neutral',
      stats: [
        { label: '最终分数', value: state.score.value },
        { label: '最大数字', value: state.maxTile.value },
        { label: '移动次数', value: state.moves.value },
        { label: '用时', value: formatDurationMmSs(state.elapsedSec.value) }
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
   * Settles the current match exactly once through the result service.
   * @param {boolean} naturalGameOver
   * @returns {Promise<void>}
   */
  async function settleGame(naturalGameOver) {
    if (state.gameStatus.value === 'ended' || state.gameStatus.value === 'settling') {
      return;
    }
    gameService.ensureSession(state);
    state.isSettling.value = true;
    state.gameStatus.value = 'settling';
    state.isPaused.value = false;
    state.stopTimer();
    state.activeTool.value = '';
    const payload = getPayload();
    let reward = 0;
    try {
      reward = await gameService.settleMatch({
        score: state.score.value,
        elapsedSec: state.elapsedSec.value,
        propUses: state.currentMatchPropUses.value,
        sessionId: state.matchSessionId.value,
        payload
      });
    } finally {
      state.isSettling.value = false;
      state.isMoving.value = false;
    }
    state.gameStatus.value = 'ended';
    openResultModal(naturalGameOver, reward);
    state.gameMessage.value = naturalGameOver ? '无可移动方向，对局结束' : '对局已结束';
  }

  return {
    resultModal,
    formatDurationMmSs,
    openResultModal,
    settleGame
  };
}

export { formatDurationMmSs };
