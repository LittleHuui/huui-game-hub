import { nowMs } from '../utils/timeService.js';

/**
 * @param {object} remote
 * @returns {object}
 */
export function mapMatchRecord(remote) {
  const durationMs = remote.durationMs;
  return {
    clientId: remote.clientId || '',
    serverId: remote.serverId || null,
    userId: remote.userId || '',
    deviceId: remote.deviceId || '',
    gameCode: remote.gameCode || '',
    mode: remote.mode || 'single',
    result: remote.result || '',
    difficulty: remote.difficultyCode || remote.difficulty || '',
    time: durationMs != null ? Math.round(Number(durationMs) / 1000) : Number(remote.time) || 0,
    score: remote.score ?? 0,
    propUses: remote.propUses || [],
    payload: remote.payload || {},
    createdAt: remote.createdAt ?? nowMs(),
    updatedAt: remote.updatedAt ?? nowMs(),
    syncedAt: remote.syncedAt ?? null,
    syncStatus: 'synced'
  };
}

/**
 * @param {object} remote
 * @returns {object}
 */
export function mapScoreRecord(remote) {
  const durationMs = remote.durationMs;
  return {
    clientId: remote.clientId || '',
    serverId: remote.serverId || null,
    userId: remote.userId || '',
    deviceId: remote.deviceId || '',
    gameCode: remote.gameCode || '',
    mode: remote.mode || 'single',
    result: remote.result || 'win',
    difficulty: remote.difficultyCode || remote.difficulty || '',
    time: durationMs != null ? Math.round(Number(durationMs) / 1000) : Number(remote.time) || 0,
    score: remote.score ?? 0,
    payload: remote.payload || {},
    createdAt: remote.createdAt ?? nowMs(),
    updatedAt: remote.updatedAt ?? nowMs(),
    syncedAt: remote.syncedAt ?? null,
    syncStatus: 'synced'
  };
}

/**
 * @param {object} row
 * @returns {object}
 */
export function mapLocalMatchToPayload(row) {
  return {
    clientId: row.clientId,
    userId: row.userId,
    deviceId: row.deviceId,
    gameCode: row.gameCode,
    mode: row.mode || 'single',
    result: row.result,
    difficultyCode: row.difficulty,
    durationMs: (Number(row.time) || 0) * 1000,
    score: row.score,
    propUses: row.propUses,
    payload: row.payload || {},
    createdAt: row.createdAt,
    updatedAt: row.updatedAt
  };
}

/**
 * @param {object} row
 * @returns {object}
 */
export function mapLocalScoreToPayload(row) {
  return {
    clientId: row.clientId,
    userId: row.userId,
    deviceId: row.deviceId,
    gameCode: row.gameCode,
    mode: row.mode || 'single',
    result: row.result || 'win',
    difficultyCode: row.difficulty,
    durationMs: (Number(row.time) || 0) * 1000,
    score: row.score,
    payload: row.payload || {},
    createdAt: row.createdAt,
    updatedAt: row.updatedAt
  };
}
