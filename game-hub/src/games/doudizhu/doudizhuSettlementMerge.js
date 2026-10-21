/**
 * 为斗地主结算视图建立唯一的玩家行。
 *
 * 身份取自对局规则结算快照；积分变动只取平台结算写入的 ``actualDelta``，
 * 不在前端根据理论分或余额推算实际结果。
 * @param {object} input
 * @param {unknown} input.theoreticalSettlements
 * @param {unknown} input.platformSettlements
 * @param {(playerId: string) => string} input.resolveNickname
 * @returns {Array<object>}
 */
export function mergeDoudizhuSettlementRows(input) {
  const {
    theoreticalSettlements,
    platformSettlements,
    resolveNickname
  } = input;
  const theoreticalList = Array.isArray(theoreticalSettlements) ? theoreticalSettlements : [];
  const platformList = Array.isArray(platformSettlements) ? platformSettlements : [];
  const theoreticalByPlayer = new Map();
  const platformByPlayer = new Map();
  const playerIds = [];
  const addPlayerId = (playerId) => {
    if (playerId && !playerIds.includes(playerId)) playerIds.push(playerId);
  };
  for (const item of theoreticalList) {
    const playerId = String(item?.playerId || '').trim();
    if (!playerId) continue;
    if (!theoreticalByPlayer.has(playerId)) theoreticalByPlayer.set(playerId, item);
    addPlayerId(playerId);
  }
  for (const item of platformList) {
    const playerId = String(item?.playerId || '').trim();
    if (playerId) {
      platformByPlayer.set(playerId, item);
      addPlayerId(playerId);
    }
  }
  const rows = [];
  for (const playerId of playerIds) {
    const theoretical = theoreticalByPlayer.get(playerId);
    const platform = platformByPlayer.get(playerId);
    const actualDeltaRaw = platform?.actualDelta;
    const actualDelta =
      actualDeltaRaw == null || actualDeltaRaw === '' ? null : Number(actualDeltaRaw);
    rows.push({
      playerId,
      nickname: resolveNickname(playerId),
      role: String(theoretical?.role || platform?.role || '').trim(),
      actualDelta: Number.isFinite(actualDelta) ? actualDelta : null
    });
  }
  return rows;
}
