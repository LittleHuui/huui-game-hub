import { unref } from 'vue';
import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import * as purchaseRepository from '../repositories/purchaseRepository.js';
import * as userRepository from '../repositories/userRepository.js';
import * as syncRepository from '../repositories/syncRepository.js';
import * as localRepo from '../repositories/localRepository.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { useUserStore } from '../stores/userStore.js';
import { useShopStore } from '../stores/shopStore.js';
import * as walletService from './walletService.js';
import * as inventoryService from './inventoryService.js';
import * as toastService from './toastService.js';

/**
 * 是否可走在线购买。
 * @returns {boolean}
 */
function canPurchaseOnline() {
  const platform = usePlatformStore();
  return platform.networkMode === 'online' && !!userRepository.resolveServerUserId();
}

/**
 * 解析商城道具售价。
 * @param {string} gameCode
 * @param {string} propCode
 * @returns {number}
 */
function resolvePropPrice(gameCode, propCode) {
  const shopStore = useShopStore();
  const item = shopStore.findItem(gameCode, propCode);
  if (item && item.price != null) {
    return Number(item.price);
  }
  return 0;
}

/**
 * 购买商城道具。
 * @param {{ propCode: string; sessionId?: import('vue').Ref | string | null; gameCode?: string }} opts
 */
export async function buyProp(opts) {
  const gameCode = opts.gameCode;
  const propCode = opts.propCode;
  if (!gameCode) {
    toastService.push('缺少 gameCode', 'warning');
    return;
  }
  const shopStore = useShopStore();
  const item = shopStore.findItem(gameCode, propCode);
  const label = item ? `购买${item.name} ×1` : `购买道具 ×1`;
  const costScore = resolvePropPrice(gameCode, propCode);

  if (canPurchaseOnline()) {
    try {
      await purchaseRemote({ propCode, gameCode });
      toastService.push(`已购买 1 张${item?.name || '道具'}`, 'success');
    } catch (e) {
      toastService.push(e.message || '购买失败', 'warning');
    }
    return;
  }
  const userStore = useUserStore();
  if ((userStore.currentUser.score || 0) < costScore) {
    toastService.push('积分不足', 'warning');
    return;
  }
  purchaseOffline({
    propCode,
    costScore,
    label,
    sessionId: opts.sessionId,
    gameCode
  });
  toastService.push(`已购买 1 张${item?.name || '道具'}`, 'success');
}

/**
 * 在线购买。
 * @param {{ propCode: string; gameCode: string }} p
 */
async function purchaseRemote(p) {
  const serverId = userRepository.resolveServerUserId();
  if (!serverId) {
    throw new Error('请先创建并登录云端账户');
  }
  const t = nowMs();
  await purchaseRepository.purchaseRemote({
    clientId: createClientId('purchase'),
    userId: serverId,
    deviceId: localRepo.getDeviceId(),
    gameCode: p.gameCode,
    propCode: p.propCode,
    quantity: 1,
    createdAt: t,
    updatedAt: t
  });
  await inventoryService.refreshGameBag(p.gameCode);
}

/**
 * 离线购买。
 * @param {{ propCode: string; costScore: number; label: string; sessionId?: unknown; gameCode: string }} p
 */
function purchaseOffline(p) {
  const sid = p.sessionId != null ? unref(p.sessionId) : null;
  walletService.ledgerCost(p.costScore, 'buy_prop', sid ? { sessionId: sid } : {}, p.gameCode);
  const t = nowMs();
  const uid = useUserStore().auth.currentUserId;
  const deviceId = localRepo.getDeviceId();
  inventoryService.pushGain(
    {
      userId: uid,
      deviceId,
      gameCode: p.gameCode,
      propCode: p.propCode,
      amount: 1,
      reason: 'buy',
      createdAt: t,
      updatedAt: t
    },
    { label: p.label, cost: p.costScore, sessionId: sid }
  );
}
