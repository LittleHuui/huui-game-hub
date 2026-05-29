/**
 * 判断字段是否满足 visibleWhen 条件。
 * @param {{ visibleWhen?: { field?: string; equals?: unknown } }} field
 * @param {Record<string, unknown>} values
 * @returns {boolean}
 */
export function isRoomConfigFieldVisible(field, values) {
  const rule = field?.visibleWhen;
  if (!rule || typeof rule !== 'object') {
    return true;
  }
  const key = String(rule.field || '').trim();
  if (!key) {
    return true;
  }
  return values[key] === rule.equals;
}

/**
 * 将后端 roomConfigSchema 字段定义转为表单控件描述。
 * @param {Array|object|null|undefined} roomConfigSchema
 * @param {Record<string, unknown>|null|undefined} valueOverrides
 * @returns {Array<{ key: string; controlType: string; label: string; value: unknown; options?: Array<{ value: string; label: string }>; min?: number; max?: number; description?: string; visibleWhen?: { field: string; equals: unknown } }>}
 */
export function buildRoomConfigFormFields(roomConfigSchema, valueOverrides) {
  if (!Array.isArray(roomConfigSchema)) {
    return [];
  }
  const fields = [];
  for (const rawField of roomConfigSchema) {
    if (!rawField || typeof rawField !== 'object') {
      continue;
    }
    const key = String(rawField.key || '').trim();
    if (!key) {
      continue;
    }
    const type = String(rawField.type || '').trim().toLowerCase();
    const label = String(rawField.label || key).trim();
    const value =
      valueOverrides && Object.prototype.hasOwnProperty.call(valueOverrides, key)
        ? valueOverrides[key]
        : rawField.defaultValue;
    const description = rawField.description ? String(rawField.description).trim() : '';
    const visibleWhen =
      rawField.visibleWhen && typeof rawField.visibleWhen === 'object'
        ? {
            field: String(rawField.visibleWhen.field || '').trim(),
            equals: rawField.visibleWhen.equals
          }
        : undefined;
    if (type === 'boolean') {
      fields.push({
        key,
        controlType: 'switch',
        label,
        value: Boolean(value),
        description,
        visibleWhen
      });
      continue;
    }
    if (type === 'number') {
      fields.push({
        key,
        controlType: 'number',
        label,
        value: Number(value),
        min: rawField.min != null ? Number(rawField.min) : undefined,
        max: rawField.max != null ? Number(rawField.max) : undefined,
        description,
        visibleWhen
      });
      continue;
    }
    if (type === 'enum') {
      const options = Array.isArray(rawField.options)
        ? rawField.options.map((item) => ({
            value: item?.value,
            label: String(item?.label || item?.value || '').trim()
          }))
        : [];
      const controlType = options.length > 0 && options.length <= 3 ? 'radio' : 'select';
      fields.push({
        key,
        controlType,
        label,
        value,
        options,
        description,
        visibleWhen
      });
    }
  }
  return fields;
}

/**
 * 根据当前表单值过滤可见字段。
 * @param {Array<{ key: string; visibleWhen?: { field: string; equals: unknown } }>} fields
 * @param {Record<string, unknown>} values
 * @returns {Array}
 */
export function filterVisibleRoomConfigFields(fields, values) {
  return (fields || []).filter((field) => isRoomConfigFieldVisible(field, values));
}

/**
 * 将配置值格式化为展示文本。
 * @param {unknown} value
 * @param {{ controlType?: string; options?: Array<{ value: unknown; label: string }> }} field
 * @returns {string}
 */
function formatRoomConfigDisplayValue(value, field) {
  if (field?.controlType === 'switch') {
    return value ? '是' : '否';
  }
  if (field?.controlType === 'radio' || field?.controlType === 'select') {
    const options = Array.isArray(field.options) ? field.options : [];
    const matched = options.find((item) => item.value === value);
    if (matched?.label) {
      return String(matched.label);
    }
  }
  if (value == null || value === '') {
    return '—';
  }
  return String(value);
}

/** @type {Record<string, number>} */
const ROOM_CONFIG_DISPLAY_KEY_PRIORITY = {
  finishMode: 120,
  remainingRealPlayerCountToEnd: 121,
  appendDeckSetWhenDrawPileEmpty: 210,
  appendDeckSetCount: 211
};

/**
 * 计算配置项展示排序权重（数值越小越靠前）。
 * @param {{ key: string; visibleWhen?: { field?: string } }} field
 * @returns {number}
 */
function resolveRoomConfigDisplayPriority(field) {
  const key = String(field?.key || '').trim();
  if (ROOM_CONFIG_DISPLAY_KEY_PRIORITY[key] != null) {
    return ROOM_CONFIG_DISPLAY_KEY_PRIORITY[key];
  }
  const parentKey = String(field?.visibleWhen?.field || '').trim();
  if (parentKey) {
    const parentPriority = ROOM_CONFIG_DISPLAY_KEY_PRIORITY[parentKey] ?? 500;
    return parentPriority + 1;
  }
  return 500;
}

/**
 * 按展示优先级排序配置字段。
 * @param {Array<{ key: string; visibleWhen?: { field?: string } }>} fields
 * @returns {Array}
 */
function sortRoomConfigDisplayFields(fields) {
  return [...(fields || [])].sort((left, right) => {
    const priorityDiff =
      resolveRoomConfigDisplayPriority(left) - resolveRoomConfigDisplayPriority(right);
    if (priorityDiff !== 0) {
      return priorityDiff;
    }
    return String(left.key || '').localeCompare(String(right.key || ''));
  });
}

/**
 * 估算将人数上限调整为 nextMaxPlayers 时需移除的 AI 数量。
 * @param {object|null|undefined} room
 * @param {number} nextMaxPlayers
 * @returns {number}
 */
export function estimateAiRemovalOnMaxPlayersChange(room, nextMaxPlayers) {
  const members = Array.isArray(room?.members) ? room.members : [];
  const activeCount = members.length;
  const normalizedMax = Number(nextMaxPlayers);
  if (!Number.isFinite(normalizedMax) || activeCount <= normalizedMax) {
    return 0;
  }
  const aiCount = members.filter((item) => item?.isAi).length;
  return Math.min(aiCount, activeCount - normalizedMax);
}

/**
 * 根据 schema 与房间配置生成 label/value 展示行。
 * @param {Array|object|null|undefined} roomConfigSchema
 * @param {Record<string, unknown>|null|undefined} roomConfig
 * @returns {Array<{ label: string; value: string }>}
 */
export function buildRoomConfigDisplayRows(roomConfigSchema, roomConfig) {
  const overrides = roomConfig && typeof roomConfig === 'object' ? roomConfig : {};
  const fields = sortRoomConfigDisplayFields(
    filterVisibleRoomConfigFields(
      buildRoomConfigFormFields(roomConfigSchema, overrides),
      overrides
    )
  );
  return fields.map((field) => ({
    label: field.label,
    value: formatRoomConfigDisplayValue(overrides[field.key] ?? field.value, field)
  }));
}

/**
 * 生成房间卡片上的配置摘要（单行）。
 * @param {Array|object|null|undefined} roomConfigSchema
 * @param {Record<string, unknown>|null|undefined} roomConfig
 * @param {string} [modeLabel]
 * @returns {string}
 */
export function buildRoomConfigSummaryText(roomConfigSchema, roomConfig, modeLabel) {
  const rows = buildRoomConfigDisplayRows(roomConfigSchema, roomConfig);
  const parts = rows.map((row) => `${row.label}: ${row.value}`);
  const mode = String(modeLabel || '').trim();
  if (mode) {
    parts.unshift(`模式: ${mode}`);
  }
  return parts.filter(Boolean).join(' · ') || '默认配置';
}

export function buildRoomConfigPayload(fields, values) {
  const payload = {};
  if (!Array.isArray(fields)) {
    return payload;
  }
  const formValues = values && typeof values === 'object' ? values : {};
  for (const field of fields) {
    if (!field || !field.key) {
      continue;
    }
    if (!isRoomConfigFieldVisible(field, formValues)) {
      continue;
    }
    payload[field.key] = formValues[field.key];
  }
  return payload;
}
