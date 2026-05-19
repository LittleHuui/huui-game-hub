import * as localRepo from '../repositories/localRepository.js';
import { remoteRepository } from '../repositories/remoteRepository.js';
import { loadLocalIntoStores } from '../repositories/localPersistRepository.js';
import * as userRepository from '../repositories/userRepository.js';
import * as syncRepository from '../repositories/syncRepository.js';
import * as historyRepository from '../repositories/historyRepository.js';
import * as walletRepository from '../repositories/walletRepository.js';
import * as inventoryRepository from '../repositories/inventoryRepository.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { useUserStore } from '../stores/userStore.js';
import { useRankingStore } from '../stores/rankingStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import * as toastService from './toastService.js';
import * as syncService from './syncService.js';
import * as gameCatalogService from './gameCatalogService.js';
import * as gameLifecycleService from './gameLifecycleService.js';

/**
 * 设置启动 loading 文案。
 * @param {string} message
 */
function setBootMessage(message) {
  const platform = usePlatformStore();
  platform.bootStatus = 'syncing';
  platform.syncMessage = message;
}

/**
 * 创建本地游客及初始流水（仅本地/离线无用户时使用）。
 */
export function createLocalGuestUser() {
  const userStore = useUserStore();
  const uid = `U_${nowMs()}`;
  const clientId = createClientId('user');
  const deviceId = localRepo.getDeviceId();
  const t = nowMs();
  userStore.addUser({
    clientId,
    serverId: null,
    userId: uid,
    username: `guest_${Math.floor(Math.random() * 9999)}`,
    nickname: '游客玩家',
    score: 0,
    totalScore: 0,
    props: { hintCard: 0, reviveCard: 0 },
    autoRevive: false,
    prefs: { neighborHoverRing: true },
    createdAt: t,
    updatedAt: t,
    serverCreatedAt: null,
    serverUpdatedAt: null,
    syncedAt: null
  });
  userStore.setCurrentUserId(uid);
  historyRepository.ensureHistoryBuckets(uid);

  const onPending = (e) => syncRepository.appendPendingEvent(e);
  walletRepository.pushWalletLedger(
    {
      userId: uid,
      deviceId,
      gameCode: 'minesweeper',
      type: 'gain',
      reason: 'initial_grant',
      amount: 500,
      createdAt: t,
      updatedAt: t,
      syncStatus: 'pending',
      payload: { note: '初始赠送积分' }
    },
    onPending
  );
  inventoryRepository.pushInventoryLedger(
    {
      userId: uid,
      deviceId,
      gameCode: 'minesweeper',
      propCode: 'hint_card',
      type: 'gain',
      amount: 3,
      reason: 'initial_grant',
      createdAt: t,
      updatedAt: t,
      syncStatus: 'pending',
      payload: {}
    },
    onPending
  );
  inventoryRepository.pushInventoryLedger(
    {
      userId: uid,
      deviceId,
      gameCode: 'minesweeper',
      propCode: 'revive_card',
      type: 'gain',
      amount: 1,
      reason: 'initial_grant',
      createdAt: t,
      updatedAt: t,
      syncStatus: 'pending',
      payload: {}
    },
    onPending
  );
}

/**
 * 登录/创建用户后继续 boot/context 与云同步。
 * @returns {Promise<void>}
 */
export async function continueAfterLogin() {
  const platform = usePlatformStore();
  const settingStore = useSettingStore();
  const repoMode = settingStore.settings.repositoryMode || 'auto';

  setBootMessage('正在获取启动上下文...');
  const serverUserId = userRepository.resolveBootUserId();
  let boot = null;
  try {
    boot = await remoteRepository.getBootContext({
      userId: serverUserId || undefined,
      deviceId: localRepo.getDeviceId(),
      clientTime: nowMs()
    });
    if (boot?.userExists === false) {
      userRepository.clearAuth();
      platform.markWaitingLogin('账号已失效，请重新登录');
      toastService.push('账号不存在或已失效，请重新登录', 'warning');
      await finalizeBootCatalog();
      return;
    }
    userRepository.applyBootContext(boot);
    if (Array.isArray(boot?.games)) {
      platform.setBootGames(boot.games);
    }
  } catch (e) {
    if (repoMode === 'remote') {
      toastService.push(e.message || '启动上下文获取失败', 'error');
      platform.markError('远程模式：启动失败');
      return;
    }
    toastService.push(e.message || '启动上下文获取失败，已使用本地数据', 'warning');
  }

  const canSync = boot?.userExists && userRepository.resolveServerUserId();
  if (canSync) {
    setBootMessage('正在同步云存档...');
    try {
      await syncService.sync();
      platform.markReady('online', '云存档已同步');
      await finalizeBootCatalog();
      return;
    } catch (e) {
      if (repoMode === 'remote') {
        toastService.push(e.message || '云存档同步失败', 'error');
        platform.markError('远程模式：同步失败');
        return;
      }
      toastService.push(e.message || '云存档同步失败，已使用本地数据', 'warning');
      platform.markReady('degraded', '云存档同步失败，已使用本地数据');
      await finalizeBootCatalog();
      return;
    }
  }

  platform.markReady('online', '已连接服务器');
  await finalizeBootCatalog();
}

/**
 * boot 后加载游戏目录；扫雷由页面 onMounted 统一 activateGame。
 * @returns {Promise<void>}
 */
async function finalizeBootCatalog() {
  const platform = usePlatformStore();
  await gameCatalogService.loadGameCatalog();
  const gameCode = platform.currentGameCode || 'minesweeper';
  if (gameCode !== 'minesweeper') {
    await gameLifecycleService.activateGame(gameCode);
  }
}

/**
 * App 启动初始化。
 */
export async function initialize() {
  const platform = usePlatformStore();
  const settingStore = useSettingStore();
  const ranking = useRankingStore();
  const userStore = useUserStore();

  setBootMessage('正在检测服务可用性...');
  platform.networkMode = 'unknown';
  platform.remoteAvailable = false;

  localRepo.migrateLegacyIfNeeded();
  loadLocalIntoStores();
  ranking.clear();

  const repoMode = settingStore.settings.repositoryMode || 'auto';

  if (repoMode === 'local') {
    if (userStore.users.length === 0) {
      createLocalGuestUser();
    }
    platform.markReady('offline', '本地模式：仅使用本机缓存，不同步云端');
    await finalizeBootCatalog();
    return;
  }

  let apiOk = false;
  try {
    await remoteRepository.healthCheck();
    apiOk = true;
  } catch {
    apiOk = false;
  }
  platform.remoteAvailable = apiOk;

  if (!apiOk) {
    ranking.clear();
    if (userStore.users.length === 0) {
      createLocalGuestUser();
    }
    if (repoMode === 'remote') {
      toastService.push('无法连接服务器', 'error');
      platform.markError('远程模式：服务不可用');
      return;
    }
    platform.markReady('offline', '离线模式：服务不可用，已加载本地缓存');
    await finalizeBootCatalog();
    return;
  }

  const currentUserId = userStore.auth.currentUserId;
  if (!currentUserId) {
    platform.markWaitingLogin('请登录或创建用户后继续');
    await finalizeBootCatalog();
    return;
  }

  await continueAfterLogin();
}
