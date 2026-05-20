import * as localRepo from './localRepository.js';
import { useUserStore } from '../stores/userStore.js';
import { useWalletStore } from '../stores/walletStore.js';
import { useInventoryStore } from '../stores/inventoryStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import { normalizeUsersList } from '../mappers/userMapper.js';
import * as walletRepository from './walletRepository.js';

/**
 * 将全部 store 状态写入 localStorage。
 */
export function persistAllLocal() {
  const userStore = useUserStore();
  const walletStore = useWalletStore();
  const inventoryStore = useInventoryStore();
  const historyStore = useHistoryStore();
  const settingStore = useSettingStore();
  localRepo.writeAuth(userStore.auth);
  localRepo.writeUsers(userStore.users);
  localRepo.writeSettings(settingStore.settings);
  localRepo.writeWalletLedgers(walletStore.walletLedgersByUser);
  localRepo.writeInventoryLedgers(inventoryStore.inventoryLedgersByUser);
  localRepo.writeInventoryBags(inventoryStore.bagByUser);
  localRepo.writePurchaseRecords(historyStore.purchaseRecordsByUser);
  localRepo.writePropUsageRecords(historyStore.propUsageRecordsByUser);
  localRepo.writeMatchRecords(historyStore.matchRecordsByUser);
  localRepo.writeScoreRecords(historyStore.scoreRecordsByUser);
  localRepo.writePendingEvents(historyStore.pendingEvents);
}

/**
 * 从本地缓存恢复各 store。
 */
export function loadLocalIntoStores() {
  const userStore = useUserStore();
  const walletStore = useWalletStore();
  const inventoryStore = useInventoryStore();
  const historyStore = useHistoryStore();
  const settingStore = useSettingStore();

  const users = localRepo.readUsers();
  normalizeUsersList(users);
  userStore.hydrateUsersList(users, localRepo.readAuth());
  walletStore.replaceAll(localRepo.readWalletLedgers());
  inventoryStore.replaceAll(localRepo.readInventoryLedgers(), localRepo.readInventoryBags());
  historyStore.replacePurchases(localRepo.readPurchaseRecords());
  historyStore.replacePropUsage(localRepo.readPropUsageRecords());
  historyStore.replaceMatches(localRepo.readMatchRecords());
  historyStore.replaceScores(localRepo.readScoreRecords());
  historyStore.setPending(localRepo.readPendingEvents());
  settingStore.replace(localRepo.readSettings());

  for (const u of userStore.users) {
    walletRepository.recomputeFromLedgers(u.userId);
  }
}
