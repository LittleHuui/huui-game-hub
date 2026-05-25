import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import { mapRemoteUserToLocal } from '../mappers/userMapper.js';
import { mapRemoteWalletToLocal } from '../mappers/walletMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import { remoteRepository } from './remoteRepository.js';
import * as localRepo from './localRepository.js';
import { persistAllLocal } from './localPersistRepository.js';
import * as inventoryRepository from './inventoryRepository.js';
import * as historyRepository from './historyRepository.js';

/**
 * 解析当前用户的服务端 userId。
 * @returns {string|null}
 */
export function resolveServerUserId() {
  const userStore = useUserStore();
  const uid = userStore.auth.currentUserId;
  const u = userStore.users.find((x) => x.userId === uid);
  if (!u) {
    return null;
  }
  if (u.serverId) {
    return u.serverId;
  }
  if (u.userId && String(u.userId).startsWith('user_')) {
    return u.userId;
  }
  return null;
}

/**
 * 解析 boot/context 请求使用的服务端 userId。
 * @returns {string|undefined}
 */
export function resolveBootUserId() {
  const resolved = resolveServerUserId();
  if (resolved) {
    return resolved;
  }
  const cid = useUserStore().auth.currentUserId;
  return cid || undefined;
}

/**
 * 本地缓存的用户列表（已由 loadLocalIntoStores 写入 store）。
 * @returns {import('../stores/userStore.js').GameUser[]}
 */
export function getCachedUserList() {
  return [...useUserStore().users];
}

/**
 * 解析有效的当前登录用户（auth.currentUserId 且存在于 users 列表）。
 * @returns {import('../stores/userStore.js').GameUser|null}
 */
export function resolveCachedCurrentUser() {
  const userStore = useUserStore();
  const currentUserId = userStore.auth.currentUserId;
  if (!currentUserId) {
    return null;
  }
  return userStore.users.find((u) => u.userId === currentUserId) || null;
}

/**
 * 设置当前登录用户并持久化本地缓存。
 * @param {string} userId
 */
export function setCurrentUser(userId) {
  const userStore = useUserStore();
  userStore.setCurrentUserId(userId);
  historyRepository.ensureHistoryBuckets(userId);
  persistAllLocal();
}

/**
 * 清空本地登录态。
 */
export function clearAuth() {
  const userStore = useUserStore();
  userStore.setCurrentUserId('');
  persistAllLocal();
}

/**
 * 应用登录/创建用户返回的会话数据。
 * @param {{ user: object; systemSetting?: object; wallet?: object; inventory?: object[] }} session
 * @returns {import('../stores/userStore.js').GameUser}
 */
export function applyAuthSession(session) {
  const userStore = useUserStore();
  const localUser = mapRemoteUserToLocal(session.user);
  if (session.wallet) {
    const scores = mapRemoteWalletToLocal(session.wallet);
    localUser.score = scores.score;
    localUser.totalScore = scores.totalScore;
  }
  const idx = userStore.users.findIndex(
    (u) => u.serverId === localUser.serverId || u.userId === localUser.userId || u.clientId === localUser.clientId
  );
  if (idx >= 0) {
    userStore.users[idx] = { ...userStore.users[idx], ...localUser };
  } else {
    userStore.addUser(localUser);
  }
  const authUserId = localUser.serverId || localUser.userId;
  userStore.setCurrentUserId(authUserId);
  const settingPayload = session.systemSetting?.setting ?? session.systemSetting;
  if (settingPayload && typeof settingPayload === 'object') {
    applySystemSettingToLocal(settingPayload);
  }
  if (session.inventory) {
    inventoryRepository.applyCloudInventory(session.inventory, authUserId);
  }
  historyRepository.ensureHistoryBuckets(authUserId);
  persistAllLocal();
  return localUser;
}

/**
 * 用户名登录。
 * @param {string} username
 * @returns {Promise<import('../stores/userStore.js').GameUser>}
 */
export async function loginUser(username) {
  const deviceId = localRepo.getDeviceId();
  const session = await remoteRepository.login({ username, deviceId });
  return applyAuthSession(session);
}

/**
 * 应用系统设置到 store。
 * @param {object} setting
 */
export function applySystemSettingToLocal(setting) {
  if (!setting || typeof setting !== 'object') {
    return;
  }
  const settingStore = useSettingStore();
  const userStore = useUserStore();
  const dataMode = setting.dataMode;
  if (dataMode === 'local' || dataMode === 'auto' || dataMode === 'remote') {
    settingStore.setRepositoryMode(dataMode);
  }
  const uid = userStore.auth.currentUserId;
  if (uid && typeof setting.enableSound === 'boolean') {
    userStore.setUserPrefs(uid, { enableSound: setting.enableSound });
  }
  if (uid && typeof setting.enableAnimation === 'boolean') {
    userStore.setUserPrefs(uid, { enableAnimation: setting.enableAnimation });
  }
}

/**
 * 合并云端用户到 store。
 * @param {object} cloudUser
 * @param {object} [wallet]
 * @param {object[]|null} [inventory]
 */
export function mergeCloudUser(cloudUser, wallet, inventory) {
  const userStore = useUserStore();
  const localUser = mapRemoteUserToLocal(cloudUser);
  if (wallet) {
    const scores = mapRemoteWalletToLocal(wallet);
    localUser.score = scores.score;
    localUser.totalScore = scores.totalScore;
  }
  const idx = userStore.users.findIndex(
    (u) => u.serverId === localUser.serverId || u.userId === localUser.userId
  );
  if (idx >= 0) {
    userStore.users[idx] = { ...userStore.users[idx], ...localUser };
  } else {
    userStore.addUser(localUser);
  }
  userStore.setCurrentUserId(localUser.userId);
  if (inventory) {
    inventoryRepository.applyCloudInventory(inventory, localUser.userId);
  }
}

/**
 * 应用启动上下文中的用户。
 * @param {object} boot
 */
export function applyBootContext(boot) {
  if (!boot || !boot.userExists || !boot.user) {
    return;
  }
  const userStore = useUserStore();
  const localUser = mapRemoteUserToLocal(boot.user);
  const idx = userStore.users.findIndex(
    (u) => u.serverId === localUser.serverId || u.userId === localUser.userId || u.clientId === localUser.clientId
  );
  if (idx >= 0) {
    const prev = userStore.users[idx];
    userStore.users[idx] = {
      ...prev,
      ...localUser,
      score: prev.score,
      totalScore: prev.totalScore,
      autoRevive: prev.autoRevive,
      prefs: prev.prefs
    };
  } else {
    userStore.addUser(localUser);
  }
  userStore.setCurrentUserId(localUser.userId);
  if (boot.systemSetting?.setting) {
    applySystemSettingToLocal(boot.systemSetting.setting);
  }
  if (Array.isArray(boot.userGameSettings)) {
    for (const row of boot.userGameSettings) {
      const code = row.gameCode;
      const st = row.setting;
      if (code && st && typeof st === 'object') {
        applyGameSettingToLocal(code, st);
      }
    }
  }
  persistAllLocal();
}

/**
 * @param {string} userId
 */
export function appendUserUpdatePending(userId) {
  const userStore = useUserStore();
  const u = userStore.users.find((x) => x.userId === userId);
  if (!u || !resolveServerUserId()) {
    return;
  }
  const t = nowMs();
  return {
    clientId: createClientId('uu'),
    eventType: 'user_update',
    createdAt: t,
    updatedAt: t,
    payload: {
      clientId: u.clientId,
      username: u.username,
      nickname: u.nickname
    }
  };
}

/**
 * 收集当前系统设置（用于云同步）。
 * @returns {object}
 */
export function collectSystemSetting() {
  const settingStore = useSettingStore();
  const userStore = useUserStore();
  const uid = userStore.auth.currentUserId;
  const u = userStore.users.find((x) => x.userId === uid);
  const prefs = u?.prefs || {};
  return {
    dataMode: settingStore.settings.repositoryMode || 'auto',
    theme: 'dark',
    autoSync: true,
    language: 'zh-CN',
    enableSound: prefs.enableSound !== false,
    enableAnimation: prefs.enableAnimation !== false
  };
}

/**
 * 收集指定游戏的用户设置（用于云同步）。
 * @param {string} userId
 * @param {string} gameCode
 * @returns {object}
 */
export function collectGameSetting(userId, gameCode) {
  const userStore = useUserStore();
  if (!userId || !gameCode) {
    return {};
  }
  return userStore.getGameSetting(userId, gameCode);
}

/**
 * 将云端游戏设置合并到本地用户。
 * @param {string} gameCode
 * @param {object} setting
 */
export function applyGameSettingToLocal(gameCode, setting) {
  if (!setting || typeof setting !== 'object' || !gameCode) {
    return;
  }
  const userStore = useUserStore();
  const uid = userStore.auth.currentUserId;
  if (!uid) {
    return;
  }
  userStore.patchGameSetting(uid, gameCode, setting);
  persistAllLocal();
}

/**
 * 合并写入当前用户指定游戏的设置字段。
 * @param {string} gameCode
 * @param {Record<string, unknown>} patch
 */
export function patchGameSettingForCurrentUser(gameCode, patch) {
  const userStore = useUserStore();
  const uid = userStore.auth.currentUserId;
  if (!uid || !gameCode) {
    return;
  }
  userStore.patchGameSetting(uid, gameCode, patch);
  persistAllLocal();
}

/**
 * 构建系统设置待同步事件。
 * @param {object} [setting] 省略时从当前 store 收集
 * @returns {object|null}
 */
export function buildSystemSettingPendingEvent(setting) {
  if (!resolveServerUserId()) {
    return null;
  }
  const t = nowMs();
  const payloadSetting =
    setting && typeof setting === 'object' ? setting : collectSystemSetting();
  return {
    clientId: createClientId('sus'),
    eventType: 'user_system_setting_update',
    createdAt: t,
    updatedAt: t,
    payload: { setting: payloadSetting }
  };
}

/**
 * 构建游戏设置待同步事件。
 * @param {string} gameCode
 * @param {object} setting
 * @returns {object|null}
 */
export function buildGameSettingPendingEvent(gameCode, setting) {
  if (!resolveServerUserId()) {
    return null;
  }
  const t = nowMs();
  return {
    clientId: createClientId('ugs'),
    eventType: 'user_game_setting_update',
    createdAt: t,
    updatedAt: t,
    payload: { gameCode, setting }
  };
}

/**
 * 远端创建用户。
 * @param {{ username: string; nickname: string }} form
 * @returns {Promise<import('../stores/userStore.js').GameUser>}
 */
export async function createRemoteUser(form) {
  const clientId = createClientId('user');
  const remote = await remoteRepository.createUser({
    clientId,
    username: form.username,
    nickname: form.nickname
  });
  const localUser = mapRemoteUserToLocal(remote);
  const userStore = useUserStore();
  userStore.addUser(localUser);
  const authUserId = localUser.serverId || localUser.userId;
  userStore.setCurrentUserId(authUserId);
  historyRepository.ensureHistoryBuckets(authUserId);
  try {
    await remoteRepository.bindUserDevice(localUser.userId, {
      clientId: createClientId('device'),
      deviceId: localRepo.getDeviceId(),
      deviceType: 'web'
    });
  } catch {
    /* 设备绑定非阻塞 */
  }
  persistAllLocal();
  return localUser;
}

/**
 * 创建本地用户。
 * @param {{ username: string; nickname: string }} form
 * @returns {string} userId
 */
export function createLocalUser(form) {
  const userStore = useUserStore();
  const uid = `U_${nowMs()}`;
  const t = nowMs();
  userStore.addUser({
    clientId: createClientId('user'),
    serverId: null,
    userId: uid,
    username: form.username,
    nickname: form.nickname,
    score: 0,
    totalScore: 0,
    autoRevive: false,
    prefs: {},
    createdAt: t,
    updatedAt: t,
    serverCreatedAt: null,
    serverUpdatedAt: null,
    syncedAt: null
  });
  userStore.setCurrentUserId(uid);
  persistAllLocal();
  return uid;
}

/**
 * 更新昵称（远端）。
 * @param {string} serverId
 * @param {string} nickname
 */
export async function updateNicknameRemote(serverId, nickname) {
  await remoteRepository.updateUserNickname(serverId, { nickname });
}
