import { GAME2048_MODE } from './game2048Config.js';

/**
 * Creates the 2048 business service for session, reward and settlement orchestration.
 * @param {{ session: object, gameConfig: import('vue').ComputedRef<object>, difficultyCode: import('vue').ComputedRef<string> }} deps
 * @returns {{ ensureSession: Function, rewardForScore: Function, recordPropUsage: Function, settleMatch: Function }}
 */
export function createGame2048Service({ session, gameConfig, difficultyCode }) {
  /**
   * Ensures the current match has a stable local session id.
   * @param {{ matchSessionId: import('vue').Ref<string|null>, currentMatchPropUses: import('vue').Ref<Array<object>> }} state
   * @returns {void}
   */
  function ensureSession(state) {
    if (!state.matchSessionId.value) {
      state.matchSessionId.value = session.newMatchSessionId();
      state.currentMatchPropUses.value = [];
    }
  }

  /**
   * Calculates platform reward from the current score and difficulty settlement config.
   * @param {number} score
   * @returns {number}
   */
  function rewardForScore(score) {
    const settlement = gameConfig.value?.settlement || {};
    const reward = Math.floor(score * Number(settlement.rewardRate || 0));
    return Math.max(Number(settlement.minReward || 0), reward);
  }

  /**
   * Records one prop usage in the current match session.
   * @param {{ matchSessionId: import('vue').Ref<string|null>, currentMatchPropUses: import('vue').Ref<Array<object>> }} state
   * @param {{ propCode: string, label: string, timerSec: number }} usage
   * @returns {void}
   */
  function recordPropUsage(state, { propCode, label, timerSec }) {
    ensureSession(state);
    session.trackPropUsage(state.currentMatchPropUses.value, {
      propCode,
      label,
      timerSec,
      sessionId: state.matchSessionId.value
    });
    session.persistLocal();
  }

  /**
   * Submits the final 2048 result to the single-player result flow.
   * @param {{ score: number, elapsedSec: number, propUses: Array<object>, sessionId: string|null, payload: object }} result
   * @returns {Promise<number>}
   */
  async function settleMatch({ score, elapsedSec, propUses, sessionId, payload }) {
    const reward = rewardForScore(score);
    await session.settleWin({
      score,
      rewardScore: reward,
      difficultyCode: difficultyCode.value,
      durationMs: Math.round(elapsedSec * 1000),
      propUses,
      sessionId,
      mode: GAME2048_MODE,
      matchPayload: payload,
      scorePayload: payload
    });
    return reward;
  }

  return {
    ensureSession,
    rewardForScore,
    recordPropUsage,
    settleMatch
  };
}
