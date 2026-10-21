import * as onlineAuthRepository from '../repositories/onlineAuthRepository.js';
import { useUserStore } from '../stores/userStore.js';
import { configureOnlineAuthContext } from '../api/onlineAuthContext.js';

export function resolveCurrentServerUserId() {
  const userStore = useUserStore();
  const currentUserId = userStore.auth.currentUserId;
  const user = userStore.users.find((item) => item.userId === currentUserId);
  if (!user) {
    return '';
  }
  if (user.serverId) {
    return user.serverId;
  }
  return String(user.userId || '').startsWith('user_') ? user.userId : '';
}

export function getCurrentAccessToken() {
  return getCurrentAuthSnapshot().accessToken;
}

export function getCurrentAuthSnapshot() {
  const serverUserId = resolveCurrentServerUserId();
  const token = onlineAuthRepository.getToken(serverUserId);
  if (!token?.accessToken) {
    return {
      serverUserId,
      accessToken: '',
      expiresAt: 0
    };
  }
  if (Number(token.expiresAt || 0) <= Date.now()) {
    onlineAuthRepository.clearToken(serverUserId);
    return {
      serverUserId,
      accessToken: '',
      expiresAt: 0
    };
  }
  return {
    serverUserId,
    accessToken: token.accessToken,
    expiresAt: Number(token.expiresAt || 0)
  };
}

export function hasCurrentAccessToken() {
  return Boolean(getCurrentAccessToken());
}

export function clearCurrentOnlineToken() {
  const serverUserId = resolveCurrentServerUserId();
  if (serverUserId) {
    onlineAuthRepository.clearToken(serverUserId);
  }
}

export function handleAuthenticationFailure() {
  handleSnapshotAuthenticationFailure(getCurrentAuthSnapshot());
}

export function handleSnapshotAuthenticationFailure(snapshot) {
  const serverUserId = String(snapshot?.serverUserId || '').trim();
  const token = onlineAuthRepository.getToken(serverUserId);
  if (
    !serverUserId ||
    serverUserId !== resolveCurrentServerUserId() ||
    String(token?.accessToken || '') !== String(snapshot?.accessToken || '')
  ) {
    return;
  }
  onlineAuthRepository.clearToken(serverUserId);
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new window.CustomEvent('game-hub-online-auth-failed', {
        detail: {
          serverUserId
        }
      })
    );
  }
}

export function initializeOnlineAuthContext() {
  configureOnlineAuthContext({
    getAuthSnapshot: getCurrentAuthSnapshot,
    onAuthenticationFailure: handleSnapshotAuthenticationFailure
  });
}
