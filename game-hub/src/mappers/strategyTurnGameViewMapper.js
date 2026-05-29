/**
 * 将策略回合 GameEvent API 项映射为前端事件对象。
 * @param {object} raw
 * @returns {object|null}
 */
export function mapStrategyTurnGameEvent(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const sequence = Number(raw.sequence);
  if (!Number.isFinite(sequence) || sequence < 0) {
    return null;
  }
  return {
    sequence,
    eventType: String(raw.eventType || '').trim(),
    playerId: raw.playerId != null ? String(raw.playerId).trim() : null,
    payload: raw.payload && typeof raw.payload === 'object' ? { ...raw.payload } : {},
    createdAt: Number(raw.createdAt) || 0
  };
}

/**
 * 将房间对局视图 API 响应映射为前端 GameView 领域对象。
 * @param {object} raw
 * @returns {object}
 */
export function mapStrategyTurnGameView(raw) {
  if (!raw || typeof raw !== 'object') {
    throw new Error('GameView 数据无效');
  }
  const version = Number(raw.version);
  if (!Number.isFinite(version) || version < 0) {
    throw new Error('GameView.version 无效');
  }
  const viewerPlayerId = String(raw.viewerPlayerId || '').trim();
  if (!viewerPlayerId) {
    throw new Error('GameView.viewerPlayerId 无效');
  }
  const publicState = raw.publicState && typeof raw.publicState === 'object' ? raw.publicState : {};
  const privateState = raw.privateState && typeof raw.privateState === 'object' ? raw.privateState : {};
  const legalActions = Array.isArray(raw.legalActions) ? raw.legalActions : [];
  const events = Array.isArray(raw.events)
    ? raw.events.map((item) => mapStrategyTurnGameEvent(item)).filter(Boolean)
    : [];
  return {
    roomId: raw.roomId != null ? String(raw.roomId).trim() : '',
    gameCode: String(raw.gameCode || '').trim(),
    phase: String(raw.phase || '').trim(),
    version,
    viewerPlayerId,
    currentPlayerId: raw.currentPlayerId != null ? String(raw.currentPlayerId).trim() : '',
    isGameOver: Boolean(raw.isGameOver),
    publicState,
    privateState,
    legalActions,
    events
  };
}
