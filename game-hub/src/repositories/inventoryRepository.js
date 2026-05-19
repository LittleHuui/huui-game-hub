import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import {
  mapRemoteInventoryToLocalProps,
  mapPropUsageRecord,
  mapLocalInventoryLedgerToPayload
} from '../mappers/inventoryMapper.js';
import { pageItems, groupByUserId } from '../mappers/sharedMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useInventoryStore } from '../stores/inventoryStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { remoteRepository } from './remoteRepository.js';
import * as localRepo from './localRepository.js';
import { ensureUserBucket } from './helpers.js';
import { resolveServerUserId } from './userRepository.js';
import { persistAllLocal } from './localPersistRepository.js';

const PAGE = { pageNum: 1, pageSize: 20 };

/**
 * 从道具流水重算背包。
 * @param {string} userId
 */
export function recomputeFromLedgers(userId) {
  const userStore = useUserStore();
  const inventoryStore = useInventoryStore();
  let hint = 0;
  let revive = 0;
  let match3Shuffle = 0;
  let match3Bomb = 0;
  const sorted = [...inventoryStore.listForUser(userId)].sort(
    (a, b) => (a.createdAt || 0) - (b.createdAt || 0)
  );
  for (const e of sorted) {
    if (e.syncStatus === 'failed') {
      continue;
    }
    const amt = Math.abs(Number(e.amount) || 0);
    if (e.propCode === 'hint_card') {
      hint += e.type === 'gain' ? amt : -amt;
    } else if (e.propCode === 'revive_card') {
      revive += e.type === 'gain' ? amt : -amt;
    } else if (e.propCode === 'match3_shuffle') {
      match3Shuffle += e.type === 'gain' ? amt : -amt;
    } else if (e.propCode === 'match3_bomb') {
      match3Bomb += e.type === 'gain' ? amt : -amt;
    }
  }
  userStore.patchUserProps(userId, {
    hintCard: Math.max(0, hint),
    reviveCard: Math.max(0, revive),
    match3Shuffle: Math.max(0, match3Shuffle),
    match3Bomb: Math.max(0, match3Bomb)
  });
}

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
    gameCode: partial.gameCode || 'minesweeper',
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
  recomputeFromLedgers(uid);
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
  persistAllLocal();
}

/**
 * @param {object[]} inventory
 * @param {string} userId
 */
export function applyCloudInventory(inventory, userId) {
  const userStore = useUserStore();
  const list = Array.isArray(inventory) ? inventory : [];
  userStore.patchUserProps(userId, mapRemoteInventoryToLocalProps(list));
}

/**
 * @param {object[]} propUsageRecords
 */
export function applyCloudPropUsage(propUsageRecords) {
  if (!Array.isArray(propUsageRecords) || !propUsageRecords.length) {
    return;
  }
  const historyStore = useHistoryStore();
  historyStore.replacePropUsage(groupByUserId(propUsageRecords.map(mapPropUsageRecord)));
}

/**
 * @param {string} userId
 * @param {string} gameCode
 */
export async function refreshInventory(serverUserId, gameCode) {
  const inventory = await remoteRepository.getInventory(serverUserId, { gameCode });
  const usagePage = await remoteRepository.getPropUsageRecords(serverUserId, { gameCode, ...PAGE });
  const userStore = useUserStore();
  const historyStore = useHistoryStore();
  const localKey = userStore.auth.currentUserId;
  const list = pageItems(inventory).length ? pageItems(inventory) : Array.isArray(inventory) ? inventory : [];
  userStore.patchUserProps(localKey, mapRemoteInventoryToLocalProps(list));
  ensureUserBucket(historyStore.propUsageRecordsByUser, localKey);
  historyStore.propUsageRecordsByUser[localKey] = pageItems(usagePage).map(mapPropUsageRecord);
  persistAllLocal();
}
