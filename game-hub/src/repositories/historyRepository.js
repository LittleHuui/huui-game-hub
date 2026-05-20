import {
  mapMatchRecord,
  mapLocalMatchToPayload,
  toLocalMatchRecord
} from '../mappers/matchMapper.js';
import { mapScoreRecord, mapLocalScoreToPayload, toLocalScoreRecord } from '../mappers/scoreMapper.js';
import { pageItems, groupByUserId } from '../mappers/sharedMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { remoteRepository } from './remoteRepository.js';
import { ensureUserBucket } from './helpers.js';
import { resolveServerUserId } from './userRepository.js';
import { persistAllLocal } from './localPersistRepository.js';
import { requireGameCode } from '../utils/requireGameCode.js';
import { sortHistoryRecordsDesc } from '../utils/historySort.js';

const PAGE = { pageNum: 1, pageSize: 20 };

/**
 * 合并远端与本地对局记录（按 clientId 去重；远端优先，本地独有条目全部保留）。
 * @param {object[]} remoteList
 * @param {object[]} localList
 * @returns {object[]}
 */
function mergeMatchRecords(remoteList, localList) {
  const byClientId = new Map();
  for (const row of remoteList) {
    if (row && row.clientId) {
      byClientId.set(row.clientId, row);
    }
  }
  for (const row of localList) {
    if (row && row.clientId && !byClientId.has(row.clientId)) {
      byClientId.set(row.clientId, row);
    }
  }
  return sortHistoryRecordsDesc(Array.from(byClientId.values()));
}

/**
 * @param {object} rec
 * @param {(event: object) => void} [onPending]
 */
export function pushMatchRecord(rec, onPending) {
  const userStore = useUserStore();
  const historyStore = useHistoryStore();
  const uid = rec.userId || userStore.auth.currentUserId;
  const row = toLocalMatchRecord(rec);
  ensureUserBucket(historyStore.matchRecordsByUser, uid);
  historyStore.matchRecordsByUser[uid].push(row);
  if (row.syncStatus !== 'synced' && resolveServerUserId() && onPending) {
    onPending({
      clientId: row.clientId,
      eventType: 'match_record',
      createdAt: row.createdAt,
      updatedAt: row.updatedAt,
      payload: mapLocalMatchToPayload(row)
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
  const row = toLocalScoreRecord(rec);
  ensureUserBucket(historyStore.scoreRecordsByUser, uid);
  historyStore.scoreRecordsByUser[uid].push(row);
  if (row.syncStatus !== 'synced' && resolveServerUserId() && onPending) {
    onPending({
      clientId: rec.clientId,
      eventType: 'score_record',
      createdAt: row.createdAt,
      updatedAt: row.updatedAt,
      payload: mapLocalScoreToPayload(row)
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
  ensureUserBucket(next, localKey);
  next[localKey] = mergeMatchRecords(remoteForCurrent, existing);

  const grouped = groupByUserId(mapped);
  for (const [uid, rows] of Object.entries(grouped)) {
    if (uid === localKey || (serverId && uid === serverId)) {
      continue;
    }
    const ex = next[uid] || [];
    next[uid] = mergeMatchRecords(rows, ex);
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
  ensureUserBucket(next, localKey);
  next[localKey] = mergeMatchRecords(remoteForCurrent, existing);

  const grouped = groupByUserId(mapped);
  for (const [uid, rows] of Object.entries(grouped)) {
    if (uid === localKey || (serverId && uid === serverId)) {
      continue;
    }
    const ex = next[uid] || [];
    next[uid] = mergeMatchRecords(rows, ex);
  }
  historyStore.scoreRecordsByUser = next;
  persistAllLocal();
}

/**
 * 将远端对局映射为本地结构，并在响应体缺 gameCode 时用查询参数补全。
 * @param {object} remote
 * @param {string} [queryGameCode]
 * @returns {object}
 */
function mapRemoteMatchForRefresh(remote, queryGameCode) {
  const mapped = mapMatchRecord(remote);
  if (!mapped.gameCode && queryGameCode) {
    mapped.gameCode = queryGameCode;
  }
  return mapped;
}

/**
 * @param {string} userId
 * @param {string} gameCode
 */
export async function refreshMatches(userId, gameCode) {
  const code = requireGameCode(gameCode, 'refreshMatches');
  const page = await remoteRepository.getMatches(userId, { gameCode: code, ...PAGE });
  const historyStore = useHistoryStore();
  const userStore = useUserStore();
  const localKey = userStore.auth.currentUserId;
  const remote = pageItems(page).map((row) => mapRemoteMatchForRefresh(row, code));
  const existing = historyStore.matchRecordsByUser[localKey] || [];
  const others = existing.filter((r) => {
    const rowCode = r.gameCode || '';
    return !rowCode || rowCode !== code;
  });
  const sameGame = existing.filter((r) => r.gameCode === code);
  ensureUserBucket(historyStore.matchRecordsByUser, localKey);
  historyStore.matchRecordsByUser[localKey] = [...others, ...mergeMatchRecords(remote, sameGame)];
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
