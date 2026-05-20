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

/**
 * 合并服务端背包快照与本地待同步流水。
 * @param {import('../stores/inventoryStore.js').InventoryLedger[]} ledgers
 * @param {Record<string, number>|null} bag
 * @param {string} gameCode
 * @returns {Record<string, number>}
 */
export function quantitiesForUserGame(ledgers, bag, gameCode) {
  if (!bag || Object.keys(bag).length === 0) {
    return aggregateQuantitiesByGame(ledgers, gameCode);
  }
  const pending = aggregateQuantitiesByGame(
    ledgers.filter((r) => r.syncStatus === 'pending' && r.gameCode === gameCode),
    gameCode
  );
  const merged = { ...bag };
  for (const code of Object.keys(pending)) {
    merged[code] = Math.max(0, (merged[code] || 0) + pending[code]);
  }
  for (const code of Object.keys(merged)) {
    merged[code] = Math.max(0, merged[code]);
  }
  return merged;
}
