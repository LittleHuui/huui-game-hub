import { getRepositoryModeRuntime } from '../utils/repositoryModeRuntime.js';
import { getOnlineAuthSnapshot, notifyOnlineAuthenticationFailure } from './onlineAuthContext.js';

const DEFAULT_TIMEOUT_MS = 8000;
const LOCAL_MODE_ERROR_CODE = 'LOCAL_MODE_REMOTE_REQUEST_BLOCKED';
const AUTH_ERROR_CODE = 10004;
const AUTH_HTTP_STATUS_CODES = new Set([401, 403]);

/**
 * 构造带 Bearer 的请求头。
 * @param {Record<string, string>} extraHeaders
 * @returns {Record<string, string>}
 */
function buildRequestHeaders(extraHeaders = {}, authSnapshot = {}) {
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...extraHeaders
  };
  const token = authSnapshot.accessToken;
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

/**
 * 发起请求并返回原始 JSON（含 ApiResponse 包装）。
 * @param {string} method
 * @param {string} url
 * @param {object | null} body
 * @param {number} timeoutMs
 * @param {Record<string, string>} extraHeaders
 * @param {{ _retriedAuth?: boolean; signal?: AbortSignal }} [options]
 * @returns {Promise<unknown>}
 */
export async function requestRawJson(
  method,
  url,
  body = null,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  extraHeaders = {},
  options = {}
) {
  if (!isRemoteRequestAllowed(url)) {
    throw createLocalModeBlockedError(url);
  }
  const authSnapshot = getOnlineAuthSnapshot();
  const controller = new AbortController();
  const externalSignal = options.signal;
  const abortFromExternal = () => controller.abort();
  if (externalSignal?.aborted) {
    controller.abort();
  } else if (externalSignal) {
    externalSignal.addEventListener('abort', abortFromExternal, { once: true });
  }
  const tid = setTimeout(() => controller.abort(), timeoutMs);
  try {
    /** @type {RequestInit} */
    const opts = {
      method,
      signal: controller.signal,
      headers: buildRequestHeaders(extraHeaders, authSnapshot)
    };
    if (body != null && method !== 'GET' && method !== 'HEAD') {
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    clearTimeout(tid);
    const raw = await readResponseBody(res);
    if (!res.ok) {
      if (isAuthenticationFailure(res.status, raw) && shouldHandleAuthenticationFailure(method, url)) {
        notifyOnlineAuthenticationFailure(authSnapshot);
      }
      throw createHttpError(res.status, raw);
    }
    if (isAuthenticationFailure(res.status, raw) && shouldHandleAuthenticationFailure(method, url)) {
      notifyOnlineAuthenticationFailure(authSnapshot);
    }
    return raw;
  } catch (e) {
    clearTimeout(tid);
    if (e && e.name === 'AbortError') {
      throw new Error(externalSignal?.aborted ? '请求已取消' : '请求超时');
    }
    throw e;
  } finally {
    externalSignal?.removeEventListener('abort', abortFromExternal);
  }
}

/**
 * 业务接口：解包 ApiResponse，成功时返回 data。
 * @param {string} method
 * @param {string} url
 * @param {object | null} body
 * @param {number} timeoutMs
 * @param {Record<string, string>} extraHeaders
 * @param {{ _retriedAuth?: boolean; signal?: AbortSignal }} [options]
 * @returns {Promise<unknown>}
 */
export async function requestJson(
  method,
  url,
  body = null,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  extraHeaders = {},
  options = {}
) {
  const raw = await requestRawJson(method, url, body, timeoutMs, extraHeaders, options);

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

/**
 * 判断请求的认证失败是否应结束当前在线会话。
 * @param {string} method
 * @param {string} url
 * @returns {boolean}
 */
function shouldHandleAuthenticationFailure(method, url) {
  const path = parseRequestPath(url);
  if (path === '/api/game-hub/auth/login' || path.startsWith('/api/game-hub/health/')) {
    return false;
  }
  if (String(method || '').toUpperCase() === 'POST' && path === '/api/game-hub/users') {
    return false;
  }
  if (isPublicReadRequest(method, path)) {
    return false;
  }
  return true;
}

/**
 * 判断公开目录、配置与排行榜请求，避免其异常响应影响已登录会话。
 * @param {string} method
 * @param {string} path
 * @returns {boolean}
 */
function isPublicReadRequest(method, path) {
  if (String(method || '').toUpperCase() !== 'GET') {
    return false;
  }
  return (
    path === '/api/game-hub/games' ||
    path === '/api/game-hub/props' ||
    path === '/api/game-hub/rankings' ||
    /^\/api\/game-hub\/games\/[^/]+\/(config|props|rule-definition)$/.test(path)
  );
}

/**
 * @param {number} status
 * @param {unknown} raw
 * @returns {boolean}
 */
function isAuthenticationFailure(status, raw) {
  return (
    AUTH_HTTP_STATUS_CODES.has(Number(status)) ||
    (raw && typeof raw === 'object' && Number(raw.code) === AUTH_ERROR_CODE)
  );
}

/**
 * @param {Response} response
 * @returns {Promise<unknown>}
 */
async function readResponseBody(response) {
  const contentType = String(response.headers.get('content-type') || '').toLowerCase();
  if (contentType.includes('application/json')) {
    return response.json();
  }
  const text = await response.text();
  return text === '' ? null : text;
}

/**
 * @param {number} status
 * @param {unknown} raw
 * @returns {Error & { status?: number, rawResponse?: unknown, code?: unknown, detail?: unknown }}
 */
function createHttpError(status, raw) {
  const message = raw && typeof raw === 'object' && raw.message ? raw.message : `HTTP ${status}`;
  const error = new Error(message);
  error.status = Number(status);
  error.rawResponse = raw;
  if (raw && typeof raw === 'object') {
    error.code = raw.code;
    error.detail = raw.detail;
  }
  return error;
}

/**
 * @param {string} url
 * @returns {string}
 */
function parseRequestPath(url) {
  try {
    return new URL(String(url || ''), window.location.origin).pathname.replace(/\/+$/, '') || '/';
  } catch {
    return String(url || '').split('?')[0].replace(/\/+$/, '') || '/';
  }
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
    return parsed.pathname.replace(/\/+$/, '') === '/api/game-hub/health/ready';
  } catch {
    return String(url || '').replace(/\/+$/, '') === '/api/game-hub/health/ready';
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
