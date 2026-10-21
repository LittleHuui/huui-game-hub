let getAuthSnapshotHandler = () => ({
  serverUserId: '',
  accessToken: '',
  expiresAt: 0
});
let authenticationFailureHandler = () => {};

export function configureOnlineAuthContext({ getAuthSnapshot, onAuthenticationFailure } = {}) {
  if (typeof getAuthSnapshot === 'function') {
    getAuthSnapshotHandler = getAuthSnapshot;
  }
  if (typeof onAuthenticationFailure === 'function') {
    authenticationFailureHandler = onAuthenticationFailure;
  }
}

export function getOnlineAuthSnapshot() {
  const snapshot = getAuthSnapshotHandler() || {};
  return {
    serverUserId: String(snapshot.serverUserId || ''),
    accessToken: String(snapshot.accessToken || ''),
    expiresAt: Number(snapshot.expiresAt || 0)
  };
}

export function notifyOnlineAuthenticationFailure(snapshot) {
  authenticationFailureHandler(snapshot || {});
}
