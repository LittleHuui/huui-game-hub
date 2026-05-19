import { mapLeaderboardEntry } from '../mappers/rankingMapper.js';
import { remoteRepository } from './remoteRepository.js';

/**
 * 拉取单难度排行榜原始数据并映射。
 * @param {string} gameCode
 * @param {string} difficultyCode
 * @param {string} [mode]
 * @param {number} [limit]
 * @returns {Promise<object[]>}
 */
export async function fetchLeaderboardDifficulty(gameCode, difficultyCode, mode = 'single', limit = 10) {
  const data = await remoteRepository.getLeaderboard({
    gameCode,
    mode,
    difficultyCode,
    limit
  });
  return Array.isArray(data?.items) ? data.items.map(mapLeaderboardEntry) : [];
}

/**
 * 按游戏、模式与难度拉取排行榜。
 * @param {string} gameCode
 * @param {string} [difficultyCode]
 * @param {string} [mode]
 * @param {number} [limit]
 * @returns {Promise<object[]>}
 */
export async function fetchGameLeaderboard(gameCode, difficultyCode, mode = 'single', limit = 10) {
  if (!difficultyCode) {
    return [];
  }
  try {
    return await fetchLeaderboardDifficulty(gameCode, difficultyCode, mode, limit);
  } catch {
    return [];
  }
}
