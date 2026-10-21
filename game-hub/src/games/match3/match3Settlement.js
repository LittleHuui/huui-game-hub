const CONTROLLED_RANDOM_VERSION = 1;
const MILLISECONDS_PER_SECOND = 1000;

/**
 * 根据已完成的棋盘动作构建一次最终成绩，不读取页面展示状态。
 * @param {object} round
 * @param {object} settlement
 * @returns {{reward: number; match: object}}
 */
export function buildMatch3Settlement(round, settlement) {
  const reward = Math.max(
    Number(settlement.minReward || 0),
    Math.floor(round.score * Number(settlement.rewardRate || 0))
  );
  const payload = { comboMax: round.comboMax, moves: round.moves, deadBoard: round.deadBoard };
  return {
    reward,
    match: {
      score: round.score,
      rewardScore: reward,
      difficultyCode: round.difficultyCode,
      durationMs: Math.round(round.elapsedSec * MILLISECONDS_PER_SECOND),
      propUses: round.propUses,
      sessionId: round.sessionId,
      mode: round.mode,
      matchPayload: { ...payload, controlledRandomVersion: CONTROLLED_RANDOM_VERSION },
      scorePayload: payload
    }
  };
}
