import * as userRepository from '../repositories/userRepository.js';
import * as syncRepository from '../repositories/syncRepository.js';
import * as walletRepository from '../repositories/walletRepository.js';
import * as inventoryRepository from '../repositories/inventoryRepository.js';
import * as purchaseRepository from '../repositories/purchaseRepository.js';
import * as historyRepository from '../repositories/historyRepository.js';
import { persistAllLocal } from '../repositories/localPersistRepository.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { useUserStore } from '../stores/userStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import * as toastService from './toastService.js';
import * as bootService from './bootService.js';
import * as syncService from './syncService.js';
import * as dataModeService from './dataModeService.js';

/**
 * 当前是否可对已绑定服务端用户发起写操作。
 * @returns {boolean}
 */
function canUpdateRemoteUser() {
  const platform = usePlatformStore();
  const settingStore = useSettingStore();
  if (settingStore.settings.repositoryMode === 'local') {
    return false;
  }
  if (!userRepository.resolveServerUserId()) {
    return false;
  }
  return (
    platform.networkMode === 'online' ||
    platform.networkMode === 'degraded' ||
    (settingStore.settings.repositoryMode === 'remote' && platform.remoteAvailable)
  );
}

/**
 * 用户名登录并继续启动同步。
 * @param {string} username
 * @returns {Promise<{ success: boolean; message?: string }>}
 */
export async function login(username) {
  const name = String(username || '').trim();
  if (!name) {
    const message = '请输入用户名';
    toastService.push(message, 'warning');
    return { success: false, message };
  }
  const platform = usePlatformStore();
  platform.bootStatus = 'syncing';
  platform.syncMessage = '正在登录...';
  try {
    await userRepository.loginUser(name);
    await bootService.continueAfterLogin();
    toastService.push('登录成功', 'success');
    return { success: true };
  } catch (e) {
    const message = e.message || '登录失败';
    platform.markWaitingLogin('请登录或创建用户后继续');
    toastService.push(message, 'error');
    return { success: false, message };
  }
}

/**
 * 创建用户并登录，随后继续启动同步。
 * @param {string} username
 * @param {string} nickname
 * @returns {Promise<{ success: boolean; message?: string }>}
 */
export async function createAndLogin(username, nickname) {
  const name = String(username || '').trim();
  const nick = String(nickname || '').trim();
  if (!name || !nick) {
    const message = '请输入用户名和昵称';
    toastService.push(message, 'warning');
    return { success: false, message };
  }
  const userStore = useUserStore();
  if (userStore.users.some((v) => v.username === name)) {
    const message = '用户名已存在';
    toastService.push(message, 'warning');
    return { success: false, message };
  }

  const platform = usePlatformStore();
  platform.bootStatus = 'syncing';
  platform.syncMessage = '正在创建用户...';
  try {
    await userRepository.createRemoteUser({ username: name, nickname: nick });
    await bootService.continueAfterLogin();
    toastService.push('用户已创建', 'success');
    return { success: true };
  } catch (e) {
    const message = e.message || '创建用户失败';
    platform.markWaitingLogin('请登录或创建用户后继续');
    toastService.push(message, 'error');
    return { success: false, message };
  }
}

/**
 * 创建用户（自动 online/offline 分支）。
 * @param {{ username: string; nickname: string }} form
 * @returns {Promise<boolean>}
 */
export async function createUser(form) {
  if (!form.username || !form.nickname) {
    toastService.push('请输入用户名和昵称', 'warning');
    return false;
  }
  const userStore = useUserStore();
  if (userStore.users.some((v) => v.username === form.username)) {
    toastService.push('用户名已存在', 'warning');
    return false;
  }

  const platform = usePlatformStore();
  const settingStore = useSettingStore();
  const tryRemote =
    platform.networkMode === 'online' ||
    platform.networkMode === 'degraded' ||
    settingStore.settings.repositoryMode === 'remote';

  if (tryRemote) {
    try {
      await userRepository.createRemoteUser(form);
      toastService.push('云端用户已创建并切换', 'success');
      return true;
    } catch (e) {
      if (settingStore.settings.repositoryMode === 'remote') {
        toastService.push(e.message || '创建用户失败', 'error');
        return false;
      }
    }
  }

  userRepository.createLocalUser(form);
  toastService.push('本地用户已创建并切换', 'success');
  return true;
}

/**
 * 切换当前用户。
 * @param {string} userId
 * @param {boolean} sessionLocked
 * @returns {boolean}
 */
export function switchUser(userId, sessionLocked) {
  if (sessionLocked) {
    toastService.push('对局进行中，无法切换用户', 'warning');
    return false;
  }
  useUserStore().setCurrentUserId(userId);
  persistAllLocal();
  return true;
}

/**
 * 更新昵称。
 * @param {string} nickname
 */
export async function updateNickname(nickname) {
  const userStore = useUserStore();
  const uid = userStore.auth.currentUserId;
  userStore.patchNickname(uid, nickname);
  const serverId = userRepository.resolveServerUserId();
  if (canUpdateRemoteUser() && serverId) {
    try {
      await userRepository.updateNicknameRemote(serverId, nickname);
    } catch (e) {
      toastService.push(e.message || '昵称更新失败', 'warning');
      const evt = userRepository.appendUserUpdatePending(uid);
      if (evt) {
        syncRepository.appendPendingEvent(evt);
      }
    }
  } else {
    const evt = userRepository.appendUserUpdatePending(uid);
    if (evt) {
      syncRepository.appendPendingEvent(evt);
    }
  }
  persistAllLocal();
}

/**
 * 将设置变更写入 pending 并尝试云同步。
 * @param {{ system?: boolean; gameCode?: string }} opts
 * @returns {Promise<void>}
 */
export async function queueSettingsSync(opts = {}) {
  const serverId = userRepository.resolveServerUserId();
  if (!serverId) {
    persistAllLocal();
    return;
  }
  const userStore = useUserStore();
  const uid = userStore.auth.currentUserId;
  if (opts.system) {
    const evt = userRepository.buildSystemSettingPendingEvent();
    if (evt) {
      syncRepository.appendPendingEvent(evt);
    }
  }
  if (opts.gameCode) {
    const setting = userRepository.collectGameSetting(uid, opts.gameCode);
    const evt = userRepository.buildGameSettingPendingEvent(opts.gameCode, setting);
    if (evt) {
      syncRepository.appendPendingEvent(evt);
    }
  }
  persistAllLocal();
  await syncService.flushPendingIfOnline();
}

/**
 * 设置数据模式。
 * @param {'auto'|'local'|'remote'} mode
 * @returns {Promise<void>}
 */
export async function setRepositoryMode(mode) {
  const result = await dataModeService.switchRepositoryMode(mode);
  if (!result.success) {
    return;
  }
  await syncService.flushPendingIfOnline();
}

/**
 * 邻居高亮偏好。
 * @param {boolean} value
 * @returns {Promise<void>}
 */
export async function setNeighborHoverRing(value) {
  const userStore = useUserStore();
  userStore.setUserPrefs(userStore.auth.currentUserId, { neighborHoverRing: !!value });
  await queueSettingsSync({ gameCode: 'minesweeper' });
}

/**
 * 模态打开时刷新远端数据。
 * @param {'ledger'|'propUsage'|'purchase'|'history'} type
 */
export async function refreshModalData(type) {
  if (!type || !syncService.canFetchRemote()) {
    return;
  }
  const serverId = userRepository.resolveServerUserId();
  if (!serverId) {
    return;
  }
  try {
    await syncService.flushPendingIfOnline();
    if (type === 'ledger') {
      await walletRepository.refreshWallet(serverId);
    } else if (type === 'propUsage') {
      await inventoryRepository.refreshInventory(serverId, 'minesweeper');
    } else if (type === 'purchase') {
      await purchaseRepository.refreshPurchases(serverId);
    } else if (type === 'history') {
      await historyRepository.refreshMatches(serverId);
    }
  } catch (e) {
    toastService.push(e.message || '数据刷新失败', 'warning');
  }
}

export function persistLocal() {
  persistAllLocal();
}
