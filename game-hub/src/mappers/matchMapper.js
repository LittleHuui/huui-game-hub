import { nowMs } from '../utils/timeService.js';

/**
 * @param {unknown} v
 * @param {string} field
 * @returns {string}
 */
function requireNonEmptyString(v, field) {
  if (v == null || v === '') {
    throw new Error(`缺少 ${field}`);
  }
  return String(v);
}

/**
 * @param {unknown} v
 * @returns {string|null}
 */
export function normalizeDifficultyCode(v) {
  if (v == null || v === '') {
    return null;
  }
  return String(v);
}

/**
 * @param {unknown} v
 * @param {string} field
 * @returns {number|null}
 */
export function normalizeDurationMs(v, field = 'durationMs') {
  if (v == null || v === '') {
    return null;
  }
  const n = Number(v);
  if (!Number.isFinite(n)) {
    throw new Error(`${field} 无效`);
  }
  return Math.round(n);
}

/**
 * @param {unknown} v
 * @returns {object[]}
 */
export function normalizePropUses(v) {
  if (!Array.isArray(v)) {
    throw new Error('propUses 必须为数组');
  }
  return v;
}

/**
 * @param {unknown} v
 * @returns {object}
 */
export function normalizePayload(v) {
  if (v == null) {
    return {};
  }
  if (typeof v !== 'object' || Array.isArray(v)) {
    throw new Error('payload 必须为对象');
  }
  return v;
}

/**
 * @param {object} remote
 * @returns {object}
 */
export function mapEntityFields(remote) {
  return {
    clientId: requireNonEmptyString(remote.clientId, 'clientId'),
    serverId: remote.serverId ?? null,
    userId: requireNonEmptyString(remote.userId, 'userId'),
    deviceId: remote.deviceId || '',
    createdAt: remote.createdAt ?? nowMs(),
    updatedAt: remote.updatedAt ?? nowMs(),
    syncedAt: remote.syncedAt ?? null
  };
}

/**
 * 从历史条目解析 gameCode（缺失则抛错）。
 * @param {object} row
 * @returns {string}
 */
export function resolveMatchGameCode(row) {
  return requireNonEmptyString(row?.gameCode, 'gameCode');
}

/**
 * 远端对局记录 → 本地统一结构。
 * @param {object} remote
 * @returns {object}
 */
export function mapMatchRecord(remote) {
  return {
    ...mapEntityFields(remote),
    gameCode: requireNonEmptyString(remote.gameCode, 'gameCode'),
    mode: requireNonEmptyString(remote.mode, 'mode'),
    difficultyCode: normalizeDifficultyCode(remote.difficultyCode),
    result: requireNonEmptyString(remote.result, 'result'),
    score: remote.score ?? 0,
    durationMs: normalizeDurationMs(remote.durationMs),
    propUses: normalizePropUses(remote.propUses ?? []),
    payload: normalizePayload(remote.payload),
    syncStatus: 'synced'
  };
}

/**
 * 写入 store 前规范化本地对局记录。
 * @param {object} rec
 * @returns {object}
 */
export function toLocalMatchRecord(rec) {
  const mapped = mapMatchRecord(rec);
  return {
    ...mapped,
    syncStatus: rec.syncStatus || mapped.syncStatus || 'pending'
  };
}

/**
 * 本地对局记录 → 同步 payload。
 * @param {object} row
 * @returns {object}
 */
export function mapLocalMatchToPayload(row) {
  return {
    clientId: requireNonEmptyString(row.clientId, 'clientId'),
    userId: requireNonEmptyString(row.userId, 'userId'),
    deviceId: row.deviceId || '',
    gameCode: requireNonEmptyString(row.gameCode, 'gameCode'),
    mode: requireNonEmptyString(row.mode, 'mode'),
    result: requireNonEmptyString(row.result, 'result'),
    difficultyCode: normalizeDifficultyCode(row.difficultyCode),
    durationMs: normalizeDurationMs(row.durationMs),
    score: row.score ?? 0,
    propUses: normalizePropUses(row.propUses ?? []),
    payload: normalizePayload(row.payload),
    createdAt: row.createdAt ?? nowMs(),
    updatedAt: row.updatedAt ?? nowMs()
  };
}
