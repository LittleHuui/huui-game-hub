/**
 * 从道具流水按游戏聚合 propCode → 数量。
 * @param {import('../stores/inventoryStore.js').InventoryLedger[]} ledgers
 * @param {string} gameCode
 * @returns {Record<string, number>}
 */
export function aggregateQuantitiesByGame(ledgers, gameCode) {
  const map = {};
  if (!Array.isArray(ledgers) || !gameCode) {
    return map;
  }
  const sorted = [...ledgers].sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));
  for (const row of sorted) {
    if (!row || row.gameCode !== gameCode || row.syncStatus === 'failed' || !row.propCode) {
      continue;
    }
    const amt = Math.abs(Number(row.amount) || 0);
    const delta = row.type === 'gain' ? amt : -amt;
    map[row.propCode] = (map[row.propCode] || 0) + delta;
  }
  for (const code of Object.keys(map)) {
    map[code] = Math.max(0, map[code]);
  }
  return map;
}
