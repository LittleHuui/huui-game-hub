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
    sortNo: rule.sortNo != null ? Number(rule.sortNo) : null,
    effectType: rule.effectType || null
  };
}
