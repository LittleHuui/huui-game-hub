<template>
  <div class="panel match3-shop">
    <div class="match3-shop-head">
      <h2>道具商店</h2>
      <button type="button" class="ghost" @click="$emit('open-purchase-records')">购买记录</button>
    </div>
    <div v-if="items.length === 0" class="empty-text">暂无可购买道具</div>
    <div v-for="item in items" v-else :key="item.propCode" class="match3-shop-item">
      <div class="match3-shop-info">
        <strong>{{ item.icon }} {{ item.name }}</strong>
        <span class="muted-small">{{ item.description || effectText(item) }}</span>
        <span class="muted-small">价格：{{ item.price }} · 持有：{{ counts[item.propCode] || 0 }}</span>
      </div>
      <div class="match3-shop-actions">
        <button type="button" @click="$emit('buy', item.propCode)">购买</button>
        <button type="button" class="success" :disabled="!canUse || (counts[item.propCode] || 0) <= 0" @click="$emit('use', item.propCode)">
          使用
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
    return '重新洗牌当前棋盘';
  }
  if (item.effectType === 'clear_area') {
    return '清除选中格周围区域';
  }
  return '游戏道具';
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
