import { createClientId } from '../utils/idService.js';

export const ACTION_INTENT_STATUS = Object.freeze({
  PENDING: 'PENDING',
  SENDING: 'SENDING',
  RETRYABLE_FAILED: 'RETRYABLE_FAILED',
  SUCCEEDED: 'SUCCEEDED',
  CONFLICTED: 'CONFLICTED'
});

const intentsByKey = new Map();

/**
 * 为动作正文生成稳定键。
 * @param {string} roomId
 * @param {number} baseVersion
 * @param {object} submission
 * @returns {string}
 */
function buildIntentKey(roomId, baseVersion, submission) {
  return `${roomId}:${baseVersion}:${JSON.stringify(submission)}`;
}

/**
 * 创建或复用同一动作意图。
 * @param {string} roomId
 * @param {number} baseVersion
 * @param {object} submission
 * @returns {object}
 */
export function getOrCreateActionIntent(roomId, baseVersion, submission, requestId = '') {
  const key = buildIntentKey(roomId, baseVersion, submission);
  const existing = intentsByKey.get(key);
  if (existing) {
    return existing;
  }
  const intent = {
    requestId: String(requestId || '').trim() || createClientId('room-action'),
    roomId,
    baseVersion,
    submission,
    status: ACTION_INTENT_STATUS.PENDING
  };
  intentsByKey.set(key, intent);
  return intent;
}

/**
 * 判断错误是否代表明确冲突。
 * @param {unknown} error
 * @returns {boolean}
 */
function isExplicitConflict(error) {
  const code = String(error?.code || '');
  const message = String(error?.message || '');
  return code === '409' || code.includes('CONFLICT') || /HTTP 409|版本冲突|幂等冲突/.test(message);
}

/**
 * 提交动作意图；重试始终复用原始请求正文。
 * @param {{roomId: string; baseVersion: number; submission: object; requestId?: string; send: (intent: object) => Promise<object>}} options
 * @returns {Promise<object>}
 */
export async function executeActionIntent(options) {
  const intent = getOrCreateActionIntent(
    options.roomId,
    options.baseVersion,
    options.submission,
    options.requestId
  );
  const key = buildIntentKey(intent.roomId, intent.baseVersion, intent.submission);
  let lastError = null;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    intent.status = ACTION_INTENT_STATUS.SENDING;
    try {
      const response = await options.send(intent);
      intent.status = ACTION_INTENT_STATUS.SUCCEEDED;
      intentsByKey.delete(key);
      return response;
    } catch (error) {
      lastError = error;
      if (isExplicitConflict(error)) {
        intent.status = ACTION_INTENT_STATUS.CONFLICTED;
        intentsByKey.delete(key);
        throw error;
      }
      intent.status = ACTION_INTENT_STATUS.RETRYABLE_FAILED;
    }
  }
  throw lastError;
}

/**
 * 清理指定房间或全部动作意图。
 * @param {string} [roomId]
 * @returns {void}
 */
export function clearActionIntents(roomId = '') {
  const normalized = String(roomId || '').trim();
  if (!normalized) {
    intentsByKey.clear();
    return;
  }
  for (const [key, intent] of intentsByKey.entries()) {
    if (intent.roomId === normalized) {
      intentsByKey.delete(key);
    }
  }
}

/**
 * 测试专用：读取待处理动作意图。
 * @returns {object[]}
 */
export function __getActionIntentsForTests() {
  return [...intentsByKey.values()];
}
