import { nowMs } from '../utils/timeService.js';
import {
  normalizeDifficultyCode,
  normalizeDurationMs,
  normalizePayload,
  mapEntityFields
} from './matchMapper.js';

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
 * 远端成绩记录 → 本地统一结构。
 * @param {object} remote
 * @returns {object}
 */
export function mapScoreRecord(remote) {
  return {
    ...mapEntityFields(remote),
    gameCode: requireNonEmptyString(remote.gameCode, 'gameCode'),
    mode: requireNonEmptyString(remote.mode, 'mode'),
    result: requireNonEmptyString(remote.result, 'result'),
    difficultyCode: normalizeDifficultyCode(remote.difficultyCode),
    score: remote.score ?? 0,
    durationMs: normalizeDurationMs(remote.durationMs),
    payload: normalizePayload(remote.payload),
    syncStatus: 'synced'
  };
}

/**
 * 本地成绩记录 → 同步 payload。
 * @param {object} row
 * @returns {object}
 */
export function mapLocalScoreToPayload(row) {
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
    payload: normalizePayload(row.payload),
    createdAt: row.createdAt ?? nowMs(),
    updatedAt: row.updatedAt ?? nowMs()
  };
}

/**
 * 写入 store 前规范化本地成绩记录。
 * @param {object} rec
 * @returns {object}
 */
export function toLocalScoreRecord(rec) {
  const mapped = mapScoreRecord(rec);
  return {
    ...mapped,
    syncStatus: rec.syncStatus || mapped.syncStatus || 'pending'
  };
}
