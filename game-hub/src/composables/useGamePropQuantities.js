import { computed, unref } from 'vue';
import { useUserStore } from '../stores/userStore.js';
import { useInventoryStore } from '../stores/inventoryStore.js';
import { quantitiesForUserGame } from '../utils/inventoryQuantity.js';

/**
 * 按 gameCode 聚合背包数量（流水 + 服务端 bag 快照）。
 * @param {import('vue').MaybeRefOrGetter<string>} gameCode
 */
export function useGamePropQuantities(gameCode) {
  const userStore = useUserStore();
  const inventoryStore = useInventoryStore();

  return computed(() => {
    const code = typeof gameCode === 'function' ? gameCode() : unref(gameCode);
    const uid = userStore.auth.currentUserId;
    if (!code || !uid) {
      return {};
    }
    return quantitiesForUserGame(
      inventoryStore.listForUser(uid),
      inventoryStore.bagForGame(uid, code),
      code
    );
  });
}
