import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import { groupByUserId } from '../mappers/sharedMapper.js';
import { mapPurchaseRecord } from '../mappers/purchaseMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useWalletStore } from '../stores/walletStore.js';
import { useInventoryStore } from '../stores/inventoryStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import * as localRepo from './localRepository.js';
import { persistAllLocal } from './localPersistRepository.js';
import * as userRepository from './userRepository.js';
import * as walletRepository from './walletRepository.js';
import * as inventoryRepository from './inventoryRepository.js';
import * as purchaseRepository from './purchaseRepository.js';
import * as historyRepository from './historyRepository.js';

/**
 * 规范化待同步事件。
 * @param {object[]} events
 * @returns {object[]}
 */
export function normalizePendingEvents(events) {
  if (!Array.isArray(events)) {
    return [];
  }
  return events
    .filter((e) => e && e.eventType)
    .map((e) => ({
      clientId: e.clientId,
      eventType: e.eventType,
      createdAt: e.createdAt ?? nowMs(),
      updatedAt: e.updatedAt ?? e.createdAt ?? nowMs(),
      payload: e.payload || {}
    }));
}

/**
 * 追加待同步事件。
 * @param {object} event
 */
export function appendPendingEvent(event) {
  const historyStore = useHistoryStore();
  const t = event.createdAt ?? nowMs();
  historyStore.pendingEvents.push({
    clientId: event.clientId || createClientId('evt'),
    eventType: event.eventType,
    createdAt: t,
    updatedAt: event.updatedAt ?? t,
    payload: event.payload || {}
  });
  localRepo.writePendingEvents(historyStore.pendingEvents);
}

/**
 * 清空已同步 pending。
 */
export function clearSyncedPending() {
  const historyStore = useHistoryStore();
  historyStore.setPending([]);
  localRepo.writePendingEvents([]);
}

/**
 * 从待同步事件中取最新的数据模式（云响应可能仍含旧 dataMode）。
 * @param {object[]} events
 * @returns {'auto'|'local'|'remote'|null}
 */
function resolvePendingDataMode(events) {
  if (!Array.isArray(events)) {
    return null;
  }
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const evt = events[i];
    if (evt?.eventType !== 'user_system_setting_update') {
      continue;
    }
    const mode = evt.payload?.setting?.dataMode;
    if (mode === 'local' || mode === 'auto' || mode === 'remote') {
      return mode;
    }
  }
  return null;
}

/**
 * 构建云同步请求体。
 * @param {number} [clientSnapshotVersion]
 */
export function buildSyncPayload(clientSnapshotVersion) {
  const historyStore = useHistoryStore();
  const snap = localRepo.readCloudSnapshot() || {};
  return {
    userId: userRepository.resolveServerUserId() || '',
    deviceId: localRepo.getDeviceId(),
    clientSnapshotVersion: clientSnapshotVersion ?? snap.clientSnapshotVersion ?? 0,
    clientTime: nowMs(),
    pendingEvents: normalizePendingEvents(historyStore.pendingEvents)
  };
}

/**
 * 将云端合并结果写入 store 与本地。
 * @param {object} cloud
 */
export function applyCloudSnapshot(cloud) {
  const userStore = useUserStore();
  const walletStore = useWalletStore();
  const inventoryStore = useInventoryStore();
  const historyStore = useHistoryStore();
  const settingStore = useSettingStore();

  if (cloud.user) {
    userRepository.mergeCloudUser(cloud.user, cloud.wallet, cloud.inventory);
  }

  walletRepository.applyCloudWallet(cloud.walletLedgers, cloud.wallet, userStore.auth.currentUserId);
  inventoryRepository.applyCloudPropUsage(cloud.propUsageRecords);

  if (Array.isArray(cloud.purchaseRecords) && cloud.purchaseRecords.length) {
    historyStore.replacePurchases(groupByUserId(cloud.purchaseRecords.map(mapPurchaseRecord)));
  }

  historyRepository.applyCloudMatches(cloud.matchRecords);
  historyRepository.applyCloudScores(cloud.scoreRecords);

  const pendingDataMode = resolvePendingDataMode(historyStore.pendingEvents);
  if (cloud.systemSetting?.setting) {
    userRepository.applySystemSettingToLocal(cloud.systemSetting.setting);
  }
  if (pendingDataMode) {
    settingStore.setRepositoryMode(pendingDataMode);
  }

  if (Array.isArray(cloud.userGameSettings)) {
    for (const row of cloud.userGameSettings) {
      const code = row.gameCode || row.game_code;
      const st = row.setting;
      if (code && st && typeof st === 'object') {
        userRepository.applyGameSettingToLocal(code, st);
      }
    }
  }

  const uid = userStore.auth.currentUserId;
  if (uid && cloud.inventory) {
    inventoryRepository.applyCloudInventory(cloud.inventory, uid);
  }

  for (const u of userStore.users) {
    walletRepository.recomputeFromLedgers(u.userId);
    inventoryRepository.recomputeFromLedgers(u.userId);
  }

  const snap = {
    clientSnapshotVersion: cloud.cloudSnapshotVersion ?? 0,
    cloudSnapshotVersion: cloud.cloudSnapshotVersion ?? 0,
    serverTime: cloud.serverTime ?? nowMs(),
    users: userStore.users,
    auth: userStore.auth,
    settings: settingStore.settings,
    walletLedgers: walletStore.walletLedgersByUser,
    inventoryLedgers: inventoryStore.inventoryLedgersByUser,
    purchaseRecords: historyStore.purchaseRecordsByUser,
    propUsageRecords: historyStore.propUsageRecordsByUser,
    matchRecords: historyStore.matchRecordsByUser,
    scoreRecords: historyStore.scoreRecordsByUser
  };
  localRepo.writeCloudSnapshot(snap);
  persistAllLocal();
}
