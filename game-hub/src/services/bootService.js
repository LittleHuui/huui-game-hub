import * as localRepo from '../repositories/localRepository.js';
import { remoteRepository } from '../repositories/remoteRepository.js';
import { loadLocalIntoStores } from '../repositories/localPersistRepository.js';
import * as userRepository from '../repositories/userRepository.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { useUserStore } from '../stores/userStore.js';
import { useRankingStore } from '../stores/rankingStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import * as toastService from './toastService.js';
import * as syncService from './syncService.js';
import * as gameCatalogService from './gameCatalogService.js';
import * as onlineService from './onlineService.js';
import * as realtimeService from './realtimeService.js';

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
 * 创建本地游客（平台积分为 0，不赠送初始积分）。
 * @returns {import('../stores/userStore.js').GameUser}
 */
export function createLocalGuestUser() {
  const userStore = useUserStore();
  const uid = `U_${nowMs()}`;
  const clientId = createClientId('user');
  const t = nowMs();
  const guest = {
    clientId,
    serverId: null,
    userId: uid,
    username: `guest_${Math.floor(Math.random() * 9999)}`,
    nickname: '游客玩家',
    score: 0,
    totalScore: 0,
    autoRevive: false,
    prefs: {},
    createdAt: t,
    updatedAt: t,
    serverCreatedAt: null,
    serverUpdatedAt: null,
    syncedAt: null
  };
  userStore.addUser(guest);
  userRepository.setCurrentUser(uid);
  return guest;
}

/**
 * 服务不可用时解析当前登录用户：优先复用本地缓存，最后才创建游客。
 * @returns {import('../stores/userStore.js').GameUser}
 */
export function resolveOfflineCurrentUser() {
  const cachedCurrent = userRepository.resolveCachedCurrentUser();
  if (cachedCurrent) {
    return cachedCurrent;
  }

  const cachedUsers = userRepository.getCachedUserList();
  if (cachedUsers.length > 0) {
    const first = cachedUsers[0];
    userRepository.setCurrentUser(first.userId);
    return first;
  }

  return createLocalGuestUser();
}

/**
 * 登录/创建用户后继续 boot/context 与云同步。
 * @param {{ preserveRepositoryMode?: boolean }} [options]
 * @returns {Promise<void>}
 */
export async function continueAfterLogin(options = {}) {
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
      await onlineService.markOffline();
      realtimeService.disconnect({ manual: true });
      userRepository.clearAuth();
      platform.markWaitingLogin('账号已失效，请重新登录');
      toastService.push('账号不存在或已失效，请重新登录', 'warning');
      await finalizeBootCatalog();
      return;
    }
    userRepository.applyBootContext(boot);
    if (options.preserveRepositoryMode === true) {
      settingStore.setRepositoryMode(repoMode);
    }
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
      if (options.preserveRepositoryMode === true) {
        settingStore.setRepositoryMode(repoMode);
      }
      platform.markReady('online', '云存档已同步');
      await activateOnlineRuntime();
      await finalizeBootCatalog();
      return;
    } catch (e) {
      if (repoMode === 'remote') {
        toastService.push(e.message || '云存档同步失败', 'error');
        platform.markError('远程模式：同步失败');
        return;
      }
      toastService.push(e.message || '云存档同步失败，已使用本地数据', 'warning');
      if (options.preserveRepositoryMode === true) {
        settingStore.setRepositoryMode(repoMode);
      }
      platform.markReady('degraded', '云存档同步失败，已使用本地数据');
      await activateOnlineRuntime();
      await finalizeBootCatalog();
      return;
    }
  }

  platform.markReady('online', '已连接服务器');
  await activateOnlineRuntime();
  await finalizeBootCatalog();
}

/**
 * boot 后加载游戏目录（具体游戏资源由游戏页 onMounted 激活）。
 * @returns {Promise<void>}
 */
async function finalizeBootCatalog() {
  await gameCatalogService.loadGameCatalog();
}

/**
 * 启动平台在线状态与实时通道。
 * @returns {Promise<void>}
 */
export async function activateOnlineRuntime() {
  if (!userRepository.resolveServerUserId()) {
    return;
  }
  try {
    await onlineService.markOnline();
    realtimeService.connect({ resetAuthFailed: true });
    onlineService.startOnlineRefresh();
  } catch (e) {
    toastService.push(e.message || '在线状态刷新失败', 'warning');
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

  loadLocalIntoStores();
  ranking.clear();

  const repoMode = settingStore.settings.repositoryMode || 'auto';

  if (repoMode === 'local') {
    resolveOfflineCurrentUser();
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
    resolveOfflineCurrentUser();
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
