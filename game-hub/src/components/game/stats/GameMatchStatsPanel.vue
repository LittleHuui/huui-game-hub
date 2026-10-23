<template>
  <div class="single-match-stats">
    <div class="single-stat-strip">
      <div v-for="stat in summaryStats" :key="stat.key || stat.label" class="single-stat">
        <span>{{ stat.label }}</span><strong>{{ stat.value }}</strong>
      </div>
      <button type="button" class="single-stat-details" :title="message || '完整对局统计'" aria-label="查看完整对局统计" @click="detailsOpen = true"><AppIcon name="more" /></button>
    </div>
    <AppModal :visible="detailsOpen" title="对局统计" @close="detailsOpen = false">
      <dl class="single-detail-list">
        <div v-for="stat in stats" :key="stat.key || stat.label"><dt>{{ stat.label }}<small v-if="stat.helper"> · {{ stat.helper }}</small></dt><dd>{{ stat.value }}</dd></div>
      </dl>
      <h3 v-if="quotas.length" class="single-detail-heading">本局道具剩余次数</h3>
      <dl class="single-detail-list"><div v-for="quota in quotas" :key="quota.label"><dt>{{ quota.label }}</dt><dd>{{ quota.used }} / {{ quota.max }}</dd></div></dl>
      <p v-if="message" class="single-detail-message">{{ message }}</p>
    </AppModal>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue';
import AppModal from '../../AppModal.vue';
import AppIcon from '../../ui/AppIcon.vue';
const props = defineProps({
  summaryKeys: { type: Array, default: () => [] },
  /** @type {import('vue').PropType<Array<{ key?: string; label: string; value: string|number; tone?: string; icon?: string; helper?: string }>>} */
  stats: {
    type: Array,
    default: () => []
  },
  quotas: {
    type: Array,
    default: () => []
  },
  message: {
    type: String,
    default: ''
  }
});


const detailsOpen = ref(false);
const summaryStats = computed(() => props.summaryKeys.length ? props.summaryKeys.map((key) => props.stats.find((stat) => stat.key === key)).filter(Boolean) : props.stats.slice(0, 4));
</script>
