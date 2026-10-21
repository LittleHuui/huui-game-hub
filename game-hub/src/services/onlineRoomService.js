import * as gameRuleDefinitionRepository from '../repositories/gameRuleDefinitionRepository.js';
import * as roomQueryService from './roomQueryService.js';
import { canFetchRemote } from './remoteGate.js';
import { getGameFrontendModule } from '../games/gameModuleRegistry.js';

/**
 * 读取在线房间默认模式（约定取注册表首个 mode）。
 * @param {string} gameCode
 * @returns {string}
 */
export function resolveOnlineRoomMode(gameCode) {
  const game = getGameFrontendModule(gameCode);
  return String(game?.displayMetadata?.modes?.[0] || '').trim() || 'classic';
}

/**
 * 拉取指定游戏规则定义，并写入房间通用上下文。
 * @param {string} gameCode
 * @returns {Promise<object>}
 */
export async function loadOnlineRuleDefinition(gameCode, options = {}) {
  const normalized = String(gameCode || '').trim();
  if (!normalized) {
    throw new Error('缺少 gameCode');
  }
  if (!canFetchRemote()) {
    throw new Error('当前为本地模式，在线房间不可用');
  }
  const data = await gameRuleDefinitionRepository.fetchRuleDefinition(normalized);
  if (options.signal?.aborted) return data;
  const fieldOrder = getGameFrontendModule(normalized)?.roomConfigFieldOrder || [];
  const schema = Array.isArray(data.roomConfigSchema) ? data.roomConfigSchema.map((field) => {
    const index = fieldOrder.indexOf(field.key);
    return { ...field, displayOrder: index >= 0 ? index : fieldOrder.length + (field.visibleWhen ? 1 : 0) };
  }) : data.roomConfigSchema;
  roomQueryService.applyRoomRuleContext({ ...data, roomConfigSchema: schema });
  return data;
}
