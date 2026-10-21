import * as userRepository from '../repositories/userRepository.js';
import { usePlatformStore } from '../stores/platformStore.js';
import * as onlineService from './onlineService.js';
import * as realtimeService from './realtimeService.js';
import * as toastService from './toastService.js';

let handlingAuthenticationFailure = false;
let initialized = false;

/**
 * 注册认证失效后的应用状态收敛处理。
 */
export function initializeOnlineAuthenticationFailureService() {
  if (initialized || typeof window === 'undefined') {
    return;
  }
  initialized = true;
  window.addEventListener('game-hub-online-auth-failed', handleAuthenticationFailureEvent);
}

/**
 * 将当前应用切换为重新登录状态。并发失败只执行一次，避免重复提示或多次跳转。
 * @param {Event} [_event]
 */
export function handleAuthenticationFailureEvent(_event) {
  if (handlingAuthenticationFailure) {
    return;
  }
  handlingAuthenticationFailure = true;
  onlineService.stopOnlineRefresh();
  realtimeService.disconnect({ manual: true });
  userRepository.clearAuth();

  const platform = usePlatformStore();
  platform.unlockGameSwitch();
  platform.markWaitingLogin('登录状态已失效，请重新登录');
  toastService.push('登录状态已失效，请重新登录', 'warning');
}

/**
 * 成功建立新会话后允许下一次认证失效处理。
 */
export function resetAuthenticationFailureState() {
  handlingAuthenticationFailure = false;
}
