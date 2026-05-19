<template>
  <div class="panel match3-shop">
    <div class="match3-shop-head">
      <h2>é“å…·å•†åº—</h2>
      <button type="button" class="ghost" @click="$emit('open-purchase-records')">è´­ä¹°è®°å½•</button>
    </div>
    <div v-if="items.length === 0" class="empty-text">æš‚æ— å¯è´­ä¹°é“å…?/div>
    <div v-for="item in items" v-else :key="item.propCode" class="match3-shop-item">
      <div class="match3-shop-info">
        <strong>{{ item.icon }} {{ item.name }}</strong>
        <span class="muted-small">{{ item.description || effectText(item) }}</span>
        <span class="muted-small">ä»·æ ¼ï¼š{{ item.price }} ï½?æŒæœ‰ï¼š{{ counts[item.propCode] || 0 }}</span>
      </div>
      <div class="match3-shop-actions">
        <button type="button" @click="$emit('buy', item.propCode)">è´­ä¹°</button>
        <button type="button" class="success" :disabled="!canUse || (counts[item.propCode] || 0) <= 0" @click="$emit('use', item.propCode)">
          ä½¿ç”¨
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, required: true },
  counts: { type: Object, required: true },
  canUse: { type: Boolean, required: true }
});

defineEmits(['buy', 'use', 'open-purchase-records']);

/**
 * @param {object} item
 * @returns {string}
 */
function effectText(item) {
  if (item.effectType === 'shuffle_board') {
    return 'é‡æ–°æ´—ç‰Œå½“å‰æ£‹ç›˜';
  }
  if (item.effectType === 'clear_area') {
    return 'æ¸…é™¤é€‰ä¸­æ ¼å‘¨å›´åŒºåŸ?;
  }
  return 'æ¸¸æˆé“å…·';
}
</script>
<style scoped>
.match3-shop {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.match3-shop-head,
.match3-shop-item,
.match3-shop-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.match3-shop-head,
.match3-shop-item {
  justify-content: space-between;
}

.match3-shop-head h2 {
  margin: 0;
}

.match3-shop-item {
  padding: 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.06);
}

.match3-shop-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>

