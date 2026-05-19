import { computed } from 'vue';
import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import * as localRepo from '../repositories/localRepository.js';
import * as syncRepository from '../repositories/syncRepository.js';
import * as userRepository from '../repositories/userRepository.js';
import * as historyRepository from '../repositories/historyRepository.js';
import { useUserStore } from '../stores/userStore.js';
import * as walletService from './walletService.js';
import * as inventoryService from './inventoryService.js';
import * as userService from './userService.js';
import * as syncService from './syncService.js';

/**
 * @param {string | (() => string) | undefined} raw
 * @returns {string}
 */
function resolveGameCode(raw) {
  if (typeof raw === 'function') {
    const v = raw();
    if (v != null && String(v).length > 0) {
      return String(v);
    }
    return 'minesweeper';
  }
  if (raw != null && String(raw).length > 0) {
    return String(raw);
  }
  return 'minesweeper';
}

/**
 * 游戏会话编排（替代 useGameHubSession）。
 * @param {{ gameCode?: string | (() => string) }} [options]
 */
export function createGameSession(options = {}) {
  const userStore = useUserStore();
  const gameCode = computed(() => resolveGameCode(options.gameCode));
  const currentUser = computed(() => userStore.currentUser);
  const currentUserId = computed(() => userStore.auth.currentUserId);

  /**
   * @param {number} amount
   * @param {string} reason
   * @param {Record<string, unknown>} [payload]
   */
  function ledgerGain(amount, reason, payload = {}) {
    walletService.ledgerGain(amount, reason, payload, gameCode.value);
  }

  /**
   * @param {number} amount
   * @param {string} reason
   * @param {Record<string, unknown>} [payload]
   */
  function ledgerCost(amount, reason, payload = {}) {
    walletService.ledgerCost(amount, reason, payload, gameCode.value);
  }

  /**
   * @param {{ propCode: string; amount?: number; reason?: string; payload?: Record<string, unknown> }} p
   */
  function recordInventoryUse(p) {
    const t = nowMs();
    const uid = userStore.auth.currentUserId;
    inventoryService.recordUse({
      userId: uid,
      deviceId: localRepo.getDeviceId(),
      gameCode: gameCode.value,
      propCode: p.propCode,
      amount: p.amount ?? 1,
      reason: p.reason ?? 'use',
      createdAt: t,
      updatedAt: t,
      payload: p.payload || {}
    });
  }

  /**
   * @param {{ result: string; score: number; difficulty: string; timeSec: number; propUses: unknown[]; mode?: string; payload?: Record<string, unknown> }} p
   */
  function appendMatchRecord(p) {
    const t = nowMs();
    const uid = userStore.auth.currentUserId;
    historyRepository.pushMatchRecord(
      {
        clientId: createClientId('mr'),
        serverId: null,
        userId: uid,
        deviceId: localRepo.getDeviceId(),
        gameCode: gameCode.value,
        mode: p.mode ?? 'single',
        result: p.result,
        difficulty: p.difficulty,
        time: p.timeSec,
        score: p.score,
        propUses: p.propUses,
        payload: p.payload || {},
        createdAt: t,
        updatedAt: t,
        syncedAt: null,
        syncStatus: 'pending'
      },
      (e) => syncRepository.appendPendingEvent(e)
    );
  }

  /**
   * @param {{ score: number; difficulty: string; timeSec: number; mode?: string; payload?: Record<string, unknown> }} p
   */
  function appendScoreRecordWin(p) {
    const t = nowMs();
    const uid = userStore.auth.currentUserId;
    historyRepository.pushScoreRecord(
      {
        clientId: createClientId('sr'),
        serverId: null,
        userId: uid,
        deviceId: localRepo.getDeviceId(),
        gameCode: gameCode.value,
        mode: p.mode ?? 'single',
        result: 'win',
        difficulty: p.difficulty,
        time: p.timeSec,
        score: p.score,
        payload: p.payload || {},
        createdAt: t,
        updatedAt: t,
        syncedAt: null,
        syncStatus: 'pending'
      },
      (e) => syncRepository.appendPendingEvent(e)
    );
  }

  /**
   * 设置踩雷自动复活偏好并同步云端。
   * @param {boolean} value
   * @returns {Promise<void>}
   */
  async function setAutoRevive(value) {
    userStore.setAutoRevive(userStore.auth.currentUserId, value);
    await userService.queueSettingsSync({ gameCode: gameCode.value });
  }

  /**
   * 新建对局 sessionId。
   * @returns {string}
   */
  function newMatchSessionId() {
    return createClientId('match');
  }

  /**
   * 记录本局道具使用（内存 + 背包流水）。
   * @param {object[]} matchPropUses
   * @param {{ type: string; label: string; timerSec: number; sessionId: string; propCode?: string }} p
   */
  function trackPropUsage(matchPropUses, p) {
    const t = nowMs();
    matchPropUses.push({
      type: p.type,
      label: p.label,
      timerSec: p.timerSec,
      createdAt: t
    });
    recordInventoryUse({
      propCode: p.propCode || (p.type === 'hint' ? 'hint_card' : 'revive_card'),
      amount: 1,
      reason: 'use',
      payload: { label: p.label, sessionId: p.sessionId, timerSec: p.timerSec }
    });
  }

  /**
   * @param {unknown[]} propUses
   * @returns {unknown[]}
   */
  function clonePropUses(propUses) {
    return JSON.parse(JSON.stringify(propUses || []));
  }

  /**
   * 结算落盘 → 云同步 → 刷新远端历史/排行榜。
   * @param {{ includeRanking?: boolean; difficultyCode?: string; mode?: string }} [opts]
   * @returns {Promise<void>}
   */
  async function finalizeSettle(opts = {}) {
    userService.persistLocal();
    await syncService.flushPendingIfOnline();
    await syncService.refreshRemoteAfterSettle({
      includeRanking: !!opts.includeRanking,
      gameCode: gameCode.value,
      difficultyCode: opts.difficultyCode,
      mode: opts.mode
    });
  }

  /**
   * 主动结束对局结算。
   * @param {{ score: number; rewardScore?: number; difficulty: string; timeSec: number; propUses: unknown[]; sessionId: string|null; mode?: string; payload?: Record<string, unknown>; matchPayload?: Record<string, unknown>; scorePayload?: Record<string, unknown> }} p
   * @returns {Promise<void>}
   */
  async function settleEnd(p) {
    ledgerGain(p.score, 'end', { sessionId: p.sessionId });
    appendMatchRecord({
      result: 'end',
      score: p.score,
      difficulty: p.difficulty,
      timeSec: p.timeSec,
      propUses: clonePropUses(p.propUses)
    });
    await finalizeSettle();
  }

  /**
   * 失败对局结算。
   * @param {{ score: number; difficulty: string; timeSec: number; propUses: unknown[]; sessionId: string|null }} p
   * @returns {Promise<void>}
   */
  async function settleFail(p) {
    ledgerGain(p.score, 'fail', { sessionId: p.sessionId });
    appendMatchRecord({
      result: 'fail',
      score: p.score,
      difficulty: p.difficulty,
      timeSec: p.timeSec,
      propUses: clonePropUses(p.propUses)
    });
    await finalizeSettle();
  }

  /**
   * 胜利对局结算。
   * @param {{ score: number; difficulty: string; timeSec: number; propUses: unknown[]; sessionId: string|null }} p
   * @returns {Promise<void>}
   */
  async function settleWin(p) {
    ledgerGain(p.rewardScore ?? p.score, 'win', { sessionId: p.sessionId });
    appendMatchRecord({
      result: 'win',
      score: p.score,
      difficulty: p.difficulty,
      timeSec: p.timeSec,
      propUses: clonePropUses(p.propUses),
      mode: p.mode,
      payload: p.matchPayload || p.payload
    });
    appendScoreRecordWin({
      score: p.score,
      difficulty: p.difficulty,
      timeSec: p.timeSec,
      mode: p.mode,
      payload: p.scorePayload || p.payload
    });
    await finalizeSettle({ includeRanking: true, difficultyCode: p.difficulty, mode: p.mode });
  }

  return {
    gameCode,
    currentUser,
    currentUserId,
    persistLocal: userService.persistLocal,
    ledgerGain,
    ledgerCost,
    recordInventoryUse,
    appendMatchRecord,
    appendScoreRecordWin,
    setAutoRevive,
    newMatchSessionId,
    trackPropUsage,
    settleEnd,
    settleFail,
    settleWin
  };
}
