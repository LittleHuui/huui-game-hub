import { createClientId } from '../utils/idService.js';
import { mapMatchRecord, mapScoreRecord, mapLocalMatchToPayload, mapLocalScoreToPayload } from '../mappers/matchMapper.js';
import { pageItems, groupByUserId } from '../mappers/sharedMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { remoteRepository } from './remoteRepository.js';
import { ensureUserBucket } from './helpers.js';
import { resolveServerUserId } from './userRepository.js';
import { persistAllLocal } from './localPersistRepository.js';

const PAGE = { pageNum: 1, pageSize: 20 };

/**
 * 合并远端与本地待同步对局记录（按 clientId 去重，保留 pending）。
 * @param {object[]} remoteList
 * @param {object[]} localPending
 * @returns {object[]}
 */
function mergeMatchRecords(remoteList, localPending) {
  const byClientId = new Map();
  for (const row of remoteList) {
    if (row && row.clientId) {
      byClientId.set(row.clientId, row);
    }
  }
  for (const row of localPending) {
    if (row && row.clientId && row.syncStatus === 'pending' && !byClientId.has(row.clientId)) {
      byClientId.set(row.clientId, row);
    }
  }
  return Array.from(byClientId.values()).sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));
}

/**
 * @param {object} rec
 * @param {(event: object) => void} [onPending]
 */
export function pushMatchRecord(rec, onPending) {
  const userStore = useUserStore();
  const historyStore = useHistoryStore();
  const uid = rec.userId || userStore.auth.currentUserId;
  ensureUserBucket(historyStore.matchRecordsByUser, uid);
  historyStore.matchRecordsByUser[uid].push(rec);
  if (rec.syncStatus !== 'synced' && resolveServerUserId() && onPending) {
    onPending({
      clientId: rec.clientId,
      eventType: 'match_record',
      createdAt: rec.createdAt,
      updatedAt: rec.updatedAt,
      payload: mapLocalMatchToPayload(rec)
    });
  }
  persistAllLocal();
}

/**
 * @param {object} rec
 * @param {(event: object) => void} [onPending]
 */
export function pushScoreRecord(rec, onPending) {
  const userStore = useUserStore();
  const historyStore = useHistoryStore();
  const uid = rec.userId || userStore.auth.currentUserId;
  ensureUserBucket(historyStore.scoreRecordsByUser, uid);
  historyStore.scoreRecordsByUser[uid].push(rec);
  if (rec.syncStatus !== 'synced' && resolveServerUserId() && onPending) {
    onPending({
      clientId: rec.clientId,
      eventType: 'score_record',
      createdAt: rec.createdAt,
      updatedAt: rec.updatedAt,
      payload: mapLocalScoreToPayload(rec)
    });
  }
  persistAllLocal();
}

/**
 * 将云端对局记录合并进本地桶（保留 pending，避免同步响应滞后时冲掉刚结束的对局）。
 * @param {object[]} matchRecords
 */
export function applyCloudMatches(matchRecords) {
  if (!Array.isArray(matchRecords) || !matchRecords.length) {
    return;
  }
  const historyStore = useHistoryStore();
  const userStore = useUserStore();
  const localKey = userStore.auth.currentUserId;
  const serverId = resolveServerUserId();
  const mapped = matchRecords.map(mapMatchRecord);
  const next = { ...historyStore.matchRecordsByUser };

  const remoteForCurrent = mapped.filter(
    (r) => r.userId === localKey || (serverId && r.userId === serverId)
  );
  const existing = next[localKey] || [];
  const pending = existing.filter((r) => r.syncStatus === 'pending');
  ensureUserBucket(next, localKey);
  next[localKey] = mergeMatchRecords(remoteForCurrent, pending);

  const grouped = groupByUserId(mapped);
  for (const [uid, rows] of Object.entries(grouped)) {
    if (uid === localKey || (serverId && uid === serverId)) {
      continue;
    }
    const ex = next[uid] || [];
    const pend = ex.filter((r) => r.syncStatus === 'pending');
    next[uid] = mergeMatchRecords(rows, pend);
  }
  historyStore.matchRecordsByUser = next;
  persistAllLocal();
}

/**
 * 将云端成绩记录合并进本地桶（保留 pending）。
 * @param {object[]} scoreRecords
 */
export function applyCloudScores(scoreRecords) {
  if (!Array.isArray(scoreRecords) || !scoreRecords.length) {
    return;
  }
  const historyStore = useHistoryStore();
  const userStore = useUserStore();
  const localKey = userStore.auth.currentUserId;
  const serverId = resolveServerUserId();
  const mapped = scoreRecords.map(mapScoreRecord);
  const next = { ...historyStore.scoreRecordsByUser };

  const remoteForCurrent = mapped.filter(
    (r) => r.userId === localKey || (serverId && r.userId === serverId)
  );
  const existing = next[localKey] || [];
  const pending = existing.filter((r) => r.syncStatus === 'pending');
  ensureUserBucket(next, localKey);
  next[localKey] = mergeMatchRecords(remoteForCurrent, pending);

  const grouped = groupByUserId(mapped);
  for (const [uid, rows] of Object.entries(grouped)) {
    if (uid === localKey || (serverId && uid === serverId)) {
      continue;
    }
    const ex = next[uid] || [];
    const pend = ex.filter((r) => r.syncStatus === 'pending');
    next[uid] = mergeMatchRecords(rows, pend);
  }
  historyStore.scoreRecordsByUser = next;
  persistAllLocal();
}

/**
 * @param {string} userId
 * @param {string} [gameCode]
 */
export async function refreshMatches(userId, gameCode = 'minesweeper') {
  const page = await remoteRepository.getMatches(userId, { gameCode, ...PAGE });
  const historyStore = useHistoryStore();
  const userStore = useUserStore();
  const localKey = userStore.auth.currentUserId;
  const remote = pageItems(page).map(mapMatchRecord);
  const local = historyStore.matchRecordsByUser[localKey] || [];
  const pendingLocal = local.filter((r) => r.syncStatus === 'pending');
  ensureUserBucket(historyStore.matchRecordsByUser, localKey);
  historyStore.matchRecordsByUser[localKey] = mergeMatchRecords(remote, pendingLocal);
  persistAllLocal();
}

/**
 * 确保用户历史桶存在。
 * @param {string} userId
 */
export function ensureHistoryBuckets(userId) {
  const historyStore = useHistoryStore();
  ensureUserBucket(historyStore.matchRecordsByUser, userId);
  ensureUserBucket(historyStore.scoreRecordsByUser, userId);
  ensureUserBucket(historyStore.purchaseRecordsByUser, userId);
}
