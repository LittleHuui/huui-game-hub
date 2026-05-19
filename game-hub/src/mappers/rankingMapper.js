/**
 * @param {object} entry
 * @returns {object}
 */
export function mapLeaderboardEntry(entry) {
  return {
    rank: entry.rank,
    userId: entry.userId,
    nickname: entry.nickname,
    score: entry.score,
    durationMs: entry.durationMs,
    createdAt: entry.createdAt
  };
}
