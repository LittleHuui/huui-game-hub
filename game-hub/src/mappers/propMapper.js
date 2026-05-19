/** propCode → 本地背包字段 */
export const PROP_LOCAL_KEYS = {
  hint_card: 'hintCard',
  revive_card: 'reviveCard',
  match3_shuffle: 'match3Shuffle',
  match3_bomb: 'match3Bomb'
};

/**
 * @param {object} rule GamePropRuleResponse
 * @param {object} [definition] PropDefinitionResponse
 * @returns {import('../stores/shopStore.js').ShopItem}
 */
export function mapGamePropRuleToShopItem(rule, definition) {
  const propCode = rule.propCode || '';
  const price =
    rule.price != null ? Number(rule.price) : definition?.basePrice != null ? Number(definition.basePrice) : 0;
  return {
    propCode,
    name: rule.propName || definition?.propName || propCode,
    description: definition?.description || '',
    icon: definition?.icon || '🎁',
    price,
    maxUsePerMatch: rule.maxUsePerMatch ?? null,
    localKey: PROP_LOCAL_KEYS[propCode] || null,
    effectType: rule.effectType || null
  };
}
