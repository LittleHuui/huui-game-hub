import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import {
  mapRemoteInventoryToBagByGame,
  mapRemoteInventoryListToQuantities,
  mapPropUsageRecord,
  mapLocalInventoryLedgerToPayload
} from '../mappers/inventoryMapper.js';
import { pageItems } from '../mappers/sharedMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useInventoryStore } from '../stores/inventoryStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { remoteRepository } from './remoteRepository.js';
import * as localRepo from './localRepository.js';
import { ensureUserBucket } from './helpers.js';
import { resolveServerUserId } from './userRepository.js';
import { persistAllLocal } from './localPersistRepository.js';
import { requireGameCode } from '../utils/requireGameCode.js';

import { captureUserDataIdentity, mapRecordsToIdentity } from './userDataIdentity.js';
import { mergeRecordsByClientId } from './recordMerge.js';

const PAGE = { pageNum: 1, pageSize: 20 };

/**
 * @param {Omit<import('../stores/inventoryStore.js').InventoryLedger, 'syncedAt' | 'serverId'>} partial
 * @param {(event: object) => void} [onPending]
 */
export function pushInventoryLedger(partial, onPending) {
  const userStore = useUserStore();
  const inventoryStore = useInventoryStore();
  const uid = partial.userId || userStore.auth.currentUserId;
  ensureUserBucket(inventoryStore.inventoryLedgersByUser, uid);
  const row = {
    clientId: partial.clientId || createClientId('il'),
    serverId: null,
    userId: uid,
    deviceId: partial.deviceId || localRepo.getDeviceId(),
    gameCode: requireGameCode(partial.gameCode, 'pushInventoryLedger'),
    propCode: partial.propCode,
    type: partial.type,
    amount: Math.abs(Number(partial.amount) || 0),
    reason: partial.reason,
    createdAt: partial.createdAt ?? nowMs(),
    updatedAt: partial.updatedAt ?? nowMs(),
    syncedAt: null,
    syncStatus: partial.syncStatus || 'pending',
    payload: partial.payload || {}
  };
  inventoryStore.inventoryLedgersByUser[uid].push(row);
  if (row.syncStatus === 'pending' && resolveServerUserId() && row.reason === 'use' && onPending) {
    onPending({
      clientId: row.clientId,
      eventType: 'prop_usage',
      createdAt: row.createdAt,
      updatedAt: row.updatedAt,
      payload: mapLocalInventoryLedgerToPayload(row)
    });
  }
  localRepo.writeInventoryLedgers(inventoryStore.inventoryLedgersByUser);
  localRepo.writeInventoryBags(inventoryStore.bagByUser);
  persistAllLocal();
}

/**
 * 应用云端背包快照（user_prop_bag）。
 * @param {object[]} inventory
 * @param {string} userId
 */
export function applyCloudInventory(inventory, userId) {
  const inventoryStore = useInventoryStore();
  const byGame = mapRemoteInventoryToBagByGame(Array.isArray(inventory) ? inventory : []);
  const knownGames = new Set([
    ...Object.keys(inventoryStore.bagByUser[userId] || {}),
    ...inventoryStore.listForUser(userId).map((row) => row.gameCode)
  ]);
  const emptyBags = Object.fromEntries([...knownGames].map((gameCode) => [gameCode, {}]));
  inventoryStore.setBagForUser(userId, { ...emptyBags, ...byGame });
  localRepo.writeInventoryBags(inventoryStore.bagByUser);
  persistAllLocal();
}

/**
 * 购买结果中的单条背包项合并进快照。
 * @param {string} userId
 * @param {object} inventoryItem
 */
export function applyPurchaseInventoryItem(userId, inventoryItem) {
  if (!inventoryItem?.propCode || !inventoryItem?.gameCode) {
    return;
  }
  const inventoryStore = useInventoryStore();
  const prev = inventoryStore.bagForGame(userId, inventoryItem.gameCode) || {};
  inventoryStore.setBagForGame(userId, inventoryItem.gameCode, {
    ...prev,
    [inventoryItem.propCode]: Math.max(0, Number(inventoryItem.quantity) || 0)
  });
  localRepo.writeInventoryBags(inventoryStore.bagByUser);
  persistAllLocal();
}

/**
 * @param {object[]} propUsageRecords
 */
export function applyCloudPropUsage(propUsageRecords, identity = captureUserDataIdentity(useUserStore())) {
  if (!Array.isArray(propUsageRecords) || !propUsageRecords.length) {
    return;
  }
  const historyStore = useHistoryStore();
  const uid = identity.localUserId;
  const mapped = mapRecordsToIdentity(propUsageRecords, mapPropUsageRecord, identity);
  historyStore.propUsageRecordsByUser[uid] = mergeRecordsByClientId(historyStore.propUsageRecordsByUser[uid], mapped);
  const confirmedIds = new Set(mapped.map((row) => row.clientId));
  for (const row of useInventoryStore().listForUser(uid)) {
    if (confirmedIds.has(row.clientId)) row.syncStatus = 'synced';
  }
}

/**
 * @param {string} serverUserId
 * @param {string} gameCode
 */
export async function refreshInventory(serverUserId, gameCode) {
  const identity = captureUserDataIdentity(useUserStore(), serverUserId);
  const inventory = await remoteRepository.getInventory(serverUserId, { gameCode });
  const usagePage = await remoteRepository.getPropUsageRecords(serverUserId, { gameCode, ...PAGE });
  const historyStore = useHistoryStore();
  const inventoryStore = useInventoryStore();
  const localKey = identity.localUserId;
  const list = pageItems(inventory).length ? pageItems(inventory) : Array.isArray(inventory) ? inventory : [];
  inventoryStore.setBagForGame(localKey, gameCode, mapRemoteInventoryListToQuantities(list));
  ensureUserBucket(historyStore.propUsageRecordsByUser, localKey);
  applyCloudPropUsage(pageItems(usagePage), identity);
  localRepo.writeInventoryBags(inventoryStore.bagByUser);
  persistAllLocal();
}
