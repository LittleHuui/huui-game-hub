/** @type {Record<string, string>} */
export const LS_KEYS = {
  AUTH: 'game_hub_auth',
  USERS: 'game_hub_users',
  SETTINGS: 'game_hub_settings',
  WALLET_LEDGERS: 'game_hub_wallet_ledgers',
  INVENTORY_LEDGERS: 'game_hub_inventory_ledgers',
  INVENTORY_BAGS: 'game_hub_inventory_bags',
  PURCHASE_RECORDS: 'game_hub_purchase_records',
  MATCH_RECORDS: 'game_hub_match_records',
  SCORE_RECORDS: 'game_hub_score_records',
  PENDING_EVENTS: 'game_hub_pending_events',
  PROP_USAGE_RECORDS: 'game_hub_prop_usage_records',
  CLOUD_SNAPSHOT: 'game_hub_cloud_snapshot',
  DEVICE: 'game_hub_device'
};

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (raw == null || raw === '') {
      return fallback;
    }
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

export function getDeviceId() {
  let id = readJson(LS_KEYS.DEVICE, '');
  if (typeof id !== 'string' || !id) {
    id = `D_${globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : String(Date.now())}`;
    writeJson(LS_KEYS.DEVICE, id);
  }
  return id;
}

export function readAuth() {
  return readJson(LS_KEYS.AUTH, { currentUserId: '' });
}

export function writeAuth(auth) {
  writeJson(LS_KEYS.AUTH, auth);
}

export function readUsers() {
  const v = readJson(LS_KEYS.USERS, []);
  return Array.isArray(v) ? v : [];
}

export function writeUsers(users) {
  writeJson(LS_KEYS.USERS, users);
}

export function readSettings() {
  return readJson(LS_KEYS.SETTINGS, {
    storageVersion: 1,
    repositoryMode: 'auto'
  });
}

export function writeSettings(settings) {
  writeJson(LS_KEYS.SETTINGS, settings);
}

export function readWalletLedgers() {
  const v = readJson(LS_KEYS.WALLET_LEDGERS, {});
  return v && typeof v === 'object' ? v : {};
}

export function writeWalletLedgers(map) {
  writeJson(LS_KEYS.WALLET_LEDGERS, map);
}

export function readInventoryLedgers() {
  const v = readJson(LS_KEYS.INVENTORY_LEDGERS, {});
  return v && typeof v === 'object' ? v : {};
}

export function writeInventoryLedgers(map) {
  writeJson(LS_KEYS.INVENTORY_LEDGERS, map);
}

export function readInventoryBags() {
  const v = readJson(LS_KEYS.INVENTORY_BAGS, {});
  return v && typeof v === 'object' ? v : {};
}

export function writeInventoryBags(map) {
  writeJson(LS_KEYS.INVENTORY_BAGS, map);
}

export function readPurchaseRecords() {
  const v = readJson(LS_KEYS.PURCHASE_RECORDS, {});
  return v && typeof v === 'object' ? v : {};
}

export function writePurchaseRecords(map) {
  writeJson(LS_KEYS.PURCHASE_RECORDS, map);
}

export function readMatchRecords() {
  const v = readJson(LS_KEYS.MATCH_RECORDS, {});
  return v && typeof v === 'object' ? v : {};
}

export function writeMatchRecords(map) {
  writeJson(LS_KEYS.MATCH_RECORDS, map);
}

export function readScoreRecords() {
  const v = readJson(LS_KEYS.SCORE_RECORDS, {});
  return v && typeof v === 'object' ? v : {};
}

export function writeScoreRecords(map) {
  writeJson(LS_KEYS.SCORE_RECORDS, map);
}

export function readPendingEvents() {
  const v = readJson(LS_KEYS.PENDING_EVENTS, []);
  return Array.isArray(v) ? v : [];
}

export function writePendingEvents(events) {
  writeJson(LS_KEYS.PENDING_EVENTS, events);
}

export function readPropUsageRecords() {
  const v = readJson(LS_KEYS.PROP_USAGE_RECORDS, {});
  return v && typeof v === 'object' ? v : {};
}

export function writePropUsageRecords(map) {
  writeJson(LS_KEYS.PROP_USAGE_RECORDS, map);
}

export function readCloudSnapshot() {
  return readJson(LS_KEYS.CLOUD_SNAPSHOT, null);
}

export function writeCloudSnapshot(snapshot) {
  writeJson(LS_KEYS.CLOUD_SNAPSHOT, snapshot);
}
