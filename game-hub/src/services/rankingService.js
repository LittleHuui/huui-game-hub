import { hasGameCapability } from '../constants/gameRegistry.js';
import * as rankingRepository from '../repositories/rankingRepository.js';
import { useRankingStore } from '../stores/rankingStore.js';
import { canFetchRemote } from './remoteGate.js';

/**
 * 按游戏能力与当前难度刷新排行榜到 store。
 * @param {string} gameCode
 * @param {string} difficultyCode
 * @param {string} mode
 * @returns {Promise<void>}
 */
export async function refreshGameLeaderboard(gameCode, difficultyCode, mode) {
  if (!hasGameCapability(gameCode, 'leaderboard')) {
    return;
  }
  if (!canFetchRemote()) {
    return;
  }
  if (!difficultyCode) {
    throw new Error('缺少 difficultyCode');
  }
  if (!mode) {
    throw new Error('缺少 mode');
  }
  const ranking = useRankingStore();
  const items = await rankingRepository.fetchGameLeaderboard(gameCode, difficultyCode, mode);
  ranking.setDifficultyItems(gameCode, difficultyCode, items, mode);
}
