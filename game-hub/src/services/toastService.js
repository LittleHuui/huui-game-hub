import { useToastStore } from '../stores/toastStore.js';

/**
 * 显示 Toast。
 * @param {string} message
 * @param {'info'|'success'|'warning'|'error'} [level]
 * @param {number} [duration]
 * @param {string|null} [toastKind]
 */
export function push(message, level = 'info', duration = 3200, toastKind = null) {
  useToastStore().push(message, level, duration, toastKind);
}
