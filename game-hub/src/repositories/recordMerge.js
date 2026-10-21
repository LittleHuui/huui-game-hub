/** Merge facts by their stable client id, retaining all local-only records. */
export function mergeRecordsByClientId(localRecords, remoteRecords) {
  const merged = new Map();
  for (const record of [...(localRecords || []), ...(remoteRecords || [])]) {
    const key = record.clientId || record.serverId || record;
    merged.set(key, record);
  }
  return [...merged.values()];
}
