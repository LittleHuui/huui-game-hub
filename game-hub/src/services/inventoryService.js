import * as inventoryRepository from '../repositories/inventoryRepository.js';
import * as purchaseRepository from '../repositories/purchaseRepository.js';
import * as syncRepository from '../repositories/syncRepository.js';
import * as userRepository from '../repositories/userRepository.js';
import { createClientId } from '../utils/idService.js';
import { persistAllLocal } from '../repositories/localPersistRepository.js';
import { canFetchRemote } from './remoteGate.js';

/**
 * 道具使用流水。
 * @param {{ propCode: string; amount?: number; reason?: string; payload?: Record<string, unknown>; gameCode?: string; deviceId: string; userId: string; createdAt: number; updatedAt: number }} p
 */
export function recordUse(p) {
  inventoryRepository.pushInventoryLedger(
    {
      userId: p.userId,
      deviceId: p.deviceId,
      gameCode: p.gameCode || 'minesweeper',
      propCode: p.propCode,
      type: 'cost',
      amount: p.amount ?? 1,
      reason: p.reason ?? 'use',
      createdAt: p.createdAt,
      updatedAt: p.updatedAt,
      syncStatus: 'pending',
      payload: p.payload || {}
    },
    (e) => syncRepository.appendPendingEvent(e)
  );
}

/**
 * 离线购买增加道具 + 购买记录。
 * @param {object} ledgerPartial
 * @param {{ label: string; cost: number; sessionId?: string | null }} purchaseMeta
 */
export function pushGain(ledgerPartial, purchaseMeta) {
  inventoryRepository.pushInventoryLedger(
    { ...ledgerPartial, type: 'gain', syncStatus: 'pending', payload: {} },
    (e) => syncRepository.appendPendingEvent(e)
  );
  purchaseRepository.pushPurchaseRecord(
    {
      clientId: createClientId('purchase'),
      serverId: null,
      userId: ledgerPartial.userId,
      deviceId: ledgerPartial.deviceId,
      gameCode: ledgerPartial.gameCode,
      propCode: ledgerPartial.propCode,
      quantity: 1,
      createdAt: ledgerPartial.createdAt,
      updatedAt: ledgerPartial.updatedAt,
      syncedAt: null,
      syncStatus: 'pending',
      payload: purchaseMeta
    },
    (e) => syncRepository.appendPendingEvent(e)
  );
}

/**
 * @param {string} serverUserId
 * @param {string} gameCode
 */
export async function refreshRemote(serverUserId, gameCode) {
  await inventoryRepository.refreshInventory(serverUserId, gameCode);
}

/**
 * 从服务端拉取当前用户指定游戏背包。
 * @param {string} gameCode
 * @returns {Promise<void>}
 */
export async function refreshGameBag(gameCode) {
  if (!canFetchRemote()) {
    return;
  }
  const serverId = userRepository.resolveServerUserId();
  if (!serverId) {
    return;
  }
  try {
    await inventoryRepository.refreshInventory(serverId, gameCode);
  } catch {
    /* 静默失败，保留本地背包 */
  }
}

/**
 * 从服务端拉取当前用户扫雷背包（GET /users/{userId}/inventory?gameCode=minesweeper）。
 * @returns {Promise<void>}
 */
export async function refreshMinesweeperBag() {
  await refreshGameBag('minesweeper');
}

export function persistLocal() {
  persistAllLocal();
}
