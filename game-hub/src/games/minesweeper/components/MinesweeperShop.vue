<template>
  <div class="panel shop-panel">
    <div class="shop-panel-head">
      <h2>道具商城</h2>
      <button type="button" class="shop-link-records" @click="$emit('open-purchase-records')">购买记录</button>
    </div>
    <div class="shop-score-strip muted-small">当前积分：{{ user.score || 0 }} ｜ 总积分：{{ user.totalScore || 0 }}</div>
    <div v-if="items.length === 0" class="empty-text" style="margin-bottom: 0">暂无在售道具</div>
    <div v-else class="shop-list">
      <article v-for="item in items" :key="item.propCode" class="shop-card">
        <div class="shop-card-head">
          <h3 class="shop-card-name">
            <span v-if="item.icon" class="shop-card-icon" aria-hidden="true">{{ item.icon }}</span>
            {{ item.name }}
          </h3>
          <span class="shop-card-bag">背包 {{ bagCount(item) }} 张</span>
        </div>
        <p class="shop-card-desc">{{ item.description }}</p>
        <div class="shop-card-actions">
          <span class="shop-card-price">{{ item.price }} 积分 / 张</span>
          <button type="button" class="warning" @click="$emit('buy', item.propCode)">购买</button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  user: { type: Object, required: true },
  items: { type: Array, required: true }
});

defineEmits(['open-purchase-records', 'buy']);

/**
 * @param {{ localKey?: string|null }} item
 * @returns {number}
 */
function bagCount(item) {
  if (!item.localKey || !props.user?.props) {
    return 0;
  }
  return props.user.props[item.localKey] || 0;
}
</script>
