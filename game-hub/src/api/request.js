const DEFAULT_TIMEOUT_MS = 8000;

/**
 * 发起请求并返回原始 JSON（含 ApiResponse 包装）。
 * @param {string} method
 * @param {string} url
 * @param {object | null} body
 * @param {number} timeoutMs
 * @returns {Promise<unknown>}
 */
export async function requestRawJson(method, url, body = null, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), timeoutMs);
  try {
    /** @type {RequestInit} */
    const opts = {
      method,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' }
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
 * @returns {Promise<unknown>}
 */
export async function requestJson(method, url, body = null, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const raw = await requestRawJson(method, url, body, timeoutMs);

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
