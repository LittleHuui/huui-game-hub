import {
  mapMatchRecord,
  mapLocalMatchToPayload,
  toLocalMatchRecord
} from '../mappers/matchMapper.js';
import { mapScoreRecord, mapLocalScoreToPayload, toLocalScoreRecord } from '../mappers/scoreMapper.js';
import { pageItems } from '../mappers/sharedMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { remoteRepository } from './remoteRepository.js';
import { ensureUserBucket } from './helpers.js';
import { resolveServerUserId } from './userRepository.js';
import { persistAllLocal } from './localPersistRepository.js';
import { requireGameCode } from '../utils/requireGameCode.js';
import { sortHistoryRecordsDesc } from '../utils/historySort.js';

import { captureUserDataIdentity, mapRecordsToIdentity } from './userDataIdentity.js';
import { mergeRecordsByClientId } from './recordMerge.js';

const PAGE = { pageNum: 1, pageSize: 20 };

/**
 * 合并远端与本地对局记录（按 clientId 去重；远端优先，本地独有条目全部保留）。
 * @param {object[]} remoteList
 * @param {object[]} localList
 * @returns {object[]}
 */
function mergeMatchRecords(remoteList, localList) {
  return sortHistoryRecordsDesc(mergeRecordsByClientId(localList, remoteList));
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
export function applyCloudMatches(matchRecords, identity = captureUserDataIdentity(useUserStore())) {
  if (!Array.isArray(matchRecords)) return;
  const historyStore = useHistoryStore();
  const uid = identity.localUserId;
  const mapped = mapRecordsToIdentity(matchRecords, mapMatchRecord, identity);
  historyStore.matchRecordsByUser[uid] = mergeMatchRecords(mapped, historyStore.matchRecordsByUser[uid]);
  persistAllLocal();
}

/**
 * 将云端成绩记录合并进本地桶（保留 pending）。
 * @param {object[]} scoreRecords
 */
export function applyCloudScores(scoreRecords, identity = captureUserDataIdentity(useUserStore())) {
  if (!Array.isArray(scoreRecords)) return;
  const historyStore = useHistoryStore();
  const uid = identity.localUserId;
  const mapped = mapRecordsToIdentity(scoreRecords, mapScoreRecord, identity);
  historyStore.scoreRecordsByUser[uid] = mergeMatchRecords(mapped, historyStore.scoreRecordsByUser[uid]);
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
  const identity = captureUserDataIdentity(useUserStore(), userId);
  const code = requireGameCode(gameCode, 'refreshMatches');
  const page = await remoteRepository.getMatches(userId, { gameCode: code, ...PAGE });
  const historyStore = useHistoryStore();
  const localKey = identity.localUserId;
  const remote = mapRecordsToIdentity(pageItems(page), (row) => mapRemoteMatchForRefresh(row, code), identity);
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
