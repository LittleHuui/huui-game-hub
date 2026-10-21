import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
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
import * as historyRepository from './historyRepository.js';
import { captureUserDataIdentity, mapRecordsToIdentity } from './userDataIdentity.js';
import { mergeRecordsByClientId } from './recordMerge.js';

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
    ownerUserId: event.ownerUserId || event.payload?.userId || useUserStore().auth.currentUserId,
    clientId: event.clientId || createClientId('evt'),
    eventType: event.eventType,
    createdAt: t,
    updatedAt: event.updatedAt ?? t,
    payload: event.payload || {}
  });
  localRepo.writePendingEvents(historyStore.pendingEvents);
}

/**
 * 仅在整批成功时确认发送快照；并发新增或修改的事件继续保留。
 */
export function clearSyncedPending(sentEvents, syncResult, identity) {
  const count = sentEvents.length;
  if (
    syncResult?.failCount !== 0 || syncResult.receivedCount !== count ||
    syncResult.successCount + syncResult.duplicateCount !== count
  ) return;
  const historyStore = useHistoryStore();
  const confirmed = new Set(sentEvents.map((event) => JSON.stringify(event)));
  historyStore.setPending(historyStore.pendingEvents.filter((event) =>
    !eventBelongsToIdentity(event, identity) ||
    !confirmed.has(JSON.stringify(normalizePendingEvents([event])[0]))
  ));
  localRepo.writePendingEvents(historyStore.pendingEvents);
}

function eventBelongsToIdentity(event, identity) {
  const owner = event.ownerUserId || event.payload?.userId;
  return Boolean(owner) && (owner === identity.localUserId || owner === identity.serverUserId);
}

export function pendingEventsForIdentity(identity) {
  return useHistoryStore().pendingEvents.filter((event) => eventBelongsToIdentity(event, identity));
}

/**
 * 构建云同步请求体。
 * @param {number} [clientSnapshotVersion]
 */
export function buildSyncPayload(clientSnapshotVersion, identity = captureUserDataIdentity(useUserStore())) {
  const snap = localRepo.readCloudSnapshot() || {};
  return {
    userId: identity.serverUserId,
    deviceId: localRepo.getDeviceId(),
    clientSnapshotVersion: clientSnapshotVersion ?? snap.clientSnapshotVersion ?? 0,
    clientTime: nowMs(),
    pendingEvents: JSON.parse(JSON.stringify(normalizePendingEvents(pendingEventsForIdentity(identity))))
  };
}

/**
 * 将云端合并结果写入 store 与本地。
 * @param {object} cloud
 */
export function applyCloudSnapshot(cloud, identity = captureUserDataIdentity(useUserStore())) {
  const userStore = useUserStore();
  const walletStore = useWalletStore();
  const inventoryStore = useInventoryStore();
  const historyStore = useHistoryStore();
  const settingStore = useSettingStore();

  if (cloud.user) {
    userRepository.mergeCloudUser(cloud.user, cloud.wallet, null, identity.localUserId);
  }

  walletRepository.applyCloudWallet(cloud.walletLedgers, cloud.wallet, identity.localUserId);
  inventoryRepository.applyCloudPropUsage(cloud.propUsageRecords, identity);

  if (Array.isArray(cloud.purchaseRecords) && cloud.purchaseRecords.length) {
    const uid = identity.localUserId;
    const purchases = mapRecordsToIdentity(cloud.purchaseRecords, mapPurchaseRecord, identity);
    historyStore.purchaseRecordsByUser[uid] = mergeRecordsByClientId(historyStore.purchaseRecordsByUser[uid], purchases);
    const confirmedIds = new Set(purchases.map((row) => row.clientId));
    for (const row of inventoryStore.listForUser(uid)) {
      if (row.type === 'gain' && confirmedIds.has(row.clientId)) row.syncStatus = 'synced';
    }
  }

  historyRepository.applyCloudMatches(cloud.matchRecords, identity);
  historyRepository.applyCloudScores(cloud.scoreRecords, identity);

  const pending = pendingEventsForIdentity(identity);
  if (cloud.systemSetting?.setting) {
    userRepository.applySystemSettingToLocal(cloud.systemSetting.setting);
  }

  if (Array.isArray(cloud.userGameSettings)) {
    for (const row of cloud.userGameSettings) {
      const code = row.gameCode;
      const st = row.setting;
      if (code && st && typeof st === 'object') {
        userRepository.applyGameSettingToLocal(code, st);
      }
    }
  }

  for (const event of pending) {
    if (event.eventType === 'user_system_setting_update') {
      userRepository.applySystemSettingToLocal(event.payload.setting);
    } else if (event.eventType === 'user_game_setting_update') {
      userRepository.applyGameSettingToLocal(event.payload.gameCode, event.payload.setting);
    }
  }

  const uid = identity.localUserId;
  if (uid && cloud.inventory) {
    inventoryRepository.applyCloudInventory(cloud.inventory, uid);
  }

  for (const u of userStore.users) {
    walletRepository.recomputeFromLedgers(u.userId);
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
    inventoryBags: inventoryStore.bagByUser,
    purchaseRecords: historyStore.purchaseRecordsByUser,
    propUsageRecords: historyStore.propUsageRecordsByUser,
    matchRecords: historyStore.matchRecordsByUser,
    scoreRecords: historyStore.scoreRecordsByUser
  };
  localRepo.writeCloudSnapshot(snap);
  persistAllLocal();
}
