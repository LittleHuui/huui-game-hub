import * as localRepo from '../repositories/localRepository.js';
import { remoteRepository } from '../repositories/remoteRepository.js';
import * as syncRepository from '../repositories/syncRepository.js';
import * as userRepository from '../repositories/userRepository.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import * as toastService from './toastService.js';
import * as historyRepository from '../repositories/historyRepository.js';
import * as rankingService from './rankingService.js';
import * as inventoryService from './inventoryService.js';
import { canFetchRemote } from './remoteGate.js';

export { canFetchRemote };

/**
 * 执行云存档同步。
 */
export async function sync() {
  const snap = localRepo.readCloudSnapshot() || {};
  const payload = syncRepository.buildSyncPayload(snap.clientSnapshotVersion ?? 0);
  const res = await remoteRepository.syncCloudSave(payload);
  syncRepository.applyCloudSnapshot(res);
  syncRepository.clearSyncedPending();
}

/**
 * 在线且有待同步事件时，将 pending 推送到云端。
 * @returns {Promise<void>}
 */
export async function flushPendingIfOnline() {
  const settingStore = useSettingStore();
  if (settingStore.settings.repositoryMode === 'local') {
    return;
  }
  const platform = usePlatformStore();
  if (platform.networkMode !== 'online' && platform.networkMode !== 'degraded') {
    return;
  }
  if (!userRepository.resolveServerUserId()) {
    return;
  }
  const historyStore = useHistoryStore();
  if (!historyStore.pendingEvents.length) {
    return;
  }
  try {
    await sync();
  } catch (e) {
    toastService.push(e.message || '云存档同步失败', 'warning');
  }
}

/**
 * 对局结算且云同步完成后，刷新历史与排行榜等远端视图。
 * @param {{ includeRanking?: boolean; gameCode?: string; difficultyCode?: string; mode?: string }} [opts]
 * @returns {Promise<void>}
 */
export async function refreshRemoteAfterSettle(opts = {}) {
  if (!canFetchRemote()) {
    return;
  }
  const serverId = userRepository.resolveServerUserId();
  if (!serverId) {
    return;
  }
  try {
    await historyRepository.refreshMatches(serverId, opts.gameCode || 'minesweeper');
  } catch {
    /* 历史刷新失败不阻断排行榜 */
  }
  await inventoryService.refreshGameBag(opts.gameCode || 'minesweeper');
  if (opts.includeRanking && opts.difficultyCode) {
    await rankingService.refreshGameLeaderboard(opts.gameCode || 'minesweeper', opts.difficultyCode, opts.mode || 'single');
  }
}
