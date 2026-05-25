import { getRepositoryModeRuntime } from '../utils/repositoryModeRuntime.js';

const DEFAULT_TIMEOUT_MS = 8000;
const LOCAL_MODE_ERROR_CODE = 'LOCAL_MODE_REMOTE_REQUEST_BLOCKED';

/**
 * 发起请求并返回原始 JSON（含 ApiResponse 包装）。
 * @param {string} method
 * @param {string} url
 * @param {object | null} body
 * @param {number} timeoutMs
 * @param {Record<string, string>} extraHeaders
 * @returns {Promise<unknown>}
 */
export async function requestRawJson(method, url, body = null, timeoutMs = DEFAULT_TIMEOUT_MS, extraHeaders = {}) {
  if (!isRemoteRequestAllowed(url)) {
    throw createLocalModeBlockedError(url);
  }
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), timeoutMs);
  try {
    /** @type {RequestInit} */
    const opts = {
      method,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...extraHeaders }
    };
    if (body != null && method !== 'GET' && method !== 'HEAD') {
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    clearTimeout(tid);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const ct = res.headers.get('content-type');
    if (ct && ct.includes('application/json')) {
      return await res.json();
    }
    const txt = await res.text();
    return txt === '' ? null : txt;
  } catch (e) {
    clearTimeout(tid);
    if (e && e.name === 'AbortError') {
      throw new Error('请求超时');
    }
    throw e;
  }
}

/**
 * 业务接口：解包 ApiResponse，成功时返回 data。
 * @param {string} method
 * @param {string} url
 * @param {object | null} body
 * @param {number} timeoutMs
 * @param {Record<string, string>} extraHeaders
 * @returns {Promise<unknown>}
 */
export async function requestJson(method, url, body = null, timeoutMs = DEFAULT_TIMEOUT_MS, extraHeaders = {}) {
  const raw = await requestRawJson(method, url, body, timeoutMs, extraHeaders);

  if (raw && typeof raw === 'object' && 'code' in raw) {
    if (raw.code !== 0 || raw.success === false) {
      const error = new Error(raw.message || '请求失败');
      error.code = raw.code;
      error.detail = raw.detail;
      error.rawResponse = raw;
      throw error;
    }
    return raw.data;
  }

  return raw;
}

export function apiBase() {
  const raw = import.meta.env.VITE_API_BASE || '';
  return String(raw).replace(/\/+$/, '');
}

export function apiUrl(path) {
  const base = apiBase();
  const p = path.startsWith('/') ? path : `/${path}`;
  return base ? `${base}${p}` : p;
}

/**
 * 读取当前数据仓库模式。
 * @returns {'auto'|'local'|'remote'}
 */
export function getRepositoryMode() {
  return getRepositoryModeRuntime();
}

/**
 * 判断本地模式下是否允许发起远端请求。
 * @param {string} url
 * @returns {boolean}
 */
export function isRemoteRequestAllowed(url) {
  if (getRepositoryMode() !== 'local') {
    return true;
  }
  return isHealthCheckUrl(url);
}

/**
 * 判断请求是否为健康检查。
 * @param {string} url
 * @returns {boolean}
 */
export function isHealthCheckUrl(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.pathname.replace(/\/+$/, '') === '/api/game-hub/health';
  } catch {
    return String(url || '').replace(/\/+$/, '') === '/api/game-hub/health';
  }
}

/**
 * 构造本地模式请求拦截错误。
 * @param {string} url
 * @returns {Error}
 */
function createLocalModeBlockedError(url) {
  const error = new Error('本地模式下已禁止远端业务请求');
  error.code = LOCAL_MODE_ERROR_CODE;
  error.url = url;
  return error;
}
