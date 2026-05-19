import { hasGameCapability } from '../constants/gameRegistry.js';
import * as rankingRepository from '../repositories/rankingRepository.js';
import { useRankingStore } from '../stores/rankingStore.js';
import { canFetchRemote } from './remoteGate.js';

/**
 * 按游戏能力与当前难度刷新排行榜到 store。
 * @param {string} gameCode
 * @param {string} [difficultyCode]
 * @param {string} [mode]
 * @returns {Promise<void>}
 */
export async function refreshGameLeaderboard(gameCode, difficultyCode, mode = 'single') {
  if (!hasGameCapability(gameCode, 'leaderboard')) {
    return;
  }
  if (!canFetchRemote()) {
    return;
  }
  if (!difficultyCode) {
    return;
  }
  const ranking = useRankingStore();
  try {
    const items = await rankingRepository.fetchGameLeaderboard(gameCode, difficultyCode, mode);
    ranking.setDifficultyItems(gameCode, difficultyCode, items, mode);
  } catch {
    ranking.setDifficultyItems(gameCode, difficultyCode, [], mode);
  }
}
