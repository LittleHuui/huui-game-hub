import {
  buildSelectionSignature,
  createPreviewRequestController
} from './previewRequestUtils.js';

/** @typedef {'IDLE' | 'LOADING' | 'VALID' | 'INVALID' | 'INCOMPLETE'} PreviewStatus */

/**
 * 构造 COMPOSED 动作提交体。
 * @param {string} actionType
 * @param {object} selection
 * @returns {{ actionType: string; input: { kind: 'COMPOSED'; selection: object } }}
 */
export function buildComposedSubmission(actionType, selection) {
  const type = String(actionType || '').trim();
  if (!type) {
    throw new Error('缺少 actionType');
  }
  const normalizedSelection =
    selection && typeof selection === 'object' ? { ...selection } : {};
  return {
    actionType: type,
    input: {
      kind: 'COMPOSED',
      selection: normalizedSelection
    }
  };
}

/**
 * 读取 COMPOSED Offer 的 capability。
 * @param {import('./actionOfferUtils.js').ComposedActionOffer|null|undefined} offer
 * @returns {import('./actionOfferUtils.js').ComposedActionCapability|null}
 */
export function readCapability(offer) {
  if (!offer || offer.interactionMode !== 'COMPOSED') {
    return null;
  }
  return offer.capability && typeof offer.capability === 'object' ? offer.capability : null;
}

/**
 * COMPOSED Offer 不直接暴露可点击枚举项。
 * @returns {object[]}
 */
export function readDisplayOptions() {
  return [];
}

/**
 * 构造 COMPOSED 动作提交（Adapter 入口）。
 * @param {string} actionType
 * @param {object} selection
 * @returns {{ actionType: string; input: { kind: 'COMPOSED'; selection: object } }}
 */
export function buildSubmission(actionType, selection) {
  return buildComposedSubmission(actionType, selection);
}

export { buildSelectionSignature, createPreviewRequestController };

/**
 * 解析预览 API 响应为前端预览状态。
 * @param {object|null|undefined} raw
 * @returns {{ status: PreviewStatus; actionType: string; summary: object; reason: string|null }}
 */
export function parsePreviewResponse(raw) {
  if (!raw || typeof raw !== 'object') {
    return {
      status: 'INVALID',
      actionType: '',
      summary: {},
      reason: '预览响应无效'
    };
  }
  const statusRaw = String(raw.status || '').trim().toUpperCase();
  /** @type {PreviewStatus} */
  const status =
    statusRaw === 'VALID' ||
    statusRaw === 'INVALID' ||
    statusRaw === 'INCOMPLETE' ||
    statusRaw === 'LOADING'
      ? statusRaw
      : 'INVALID';
  return {
    status,
    actionType: String(raw.actionType || '').trim(),
    summary: raw.summary && typeof raw.summary === 'object' ? { ...raw.summary } : {},
    reason: raw.reason != null ? String(raw.reason).trim() : null
  };
}

/**
 * 解析提示 API 响应。
 * @param {object|null|undefined} raw
 * @returns {{ items: object[]; nextCursor: string|null }}
 */
export function parseSuggestionsResponse(raw) {
  if (!raw || typeof raw !== 'object') {
    return { items: [], nextCursor: null };
  }
  const items = Array.isArray(raw.items) ? raw.items : [];
  const nextCursor = raw.nextCursor != null ? String(raw.nextCursor) : null;
  return { items, nextCursor };
}

/**
 * 从提示候选提取 cardInstanceIds。
 * @param {object|null|undefined} candidate
 * @returns {string[]}
 */
export function extractCardInstanceIdsFromSuggestion(candidate) {
  const selection = candidate?.selection;
  const ids = Array.isArray(selection?.cardInstanceIds) ? selection.cardInstanceIds : [];
  return ids.map((id) => String(id || '').trim()).filter(Boolean);
}

export const ComposedActionAdapter = Object.freeze({
  readDisplayOptions,
  readCapability,
  buildSubmission,
  buildComposedSubmission,
  createPreviewRequestController,
  parsePreviewResponse,
  parseSuggestionsResponse,
  extractCardInstanceIdsFromSuggestion
});
