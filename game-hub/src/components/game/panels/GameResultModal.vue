<template>
  <AppModal :visible="visible" :title="title" @close="$emit('close')">
    <div class="game-result-card" :class="`game-result-card--${resultType}`">
      <p v-if="subtitle" class="game-result-subtitle">{{ subtitle }}</p>
      <section class="game-result-body hub-scrollbar">
        <section v-if="stats.length" class="game-result-section">
          <h3 class="game-result-section__label">数据统计</h3>
          <dl class="game-result-kv">
            <div
              v-for="(item, index) in stats"
              :key="`stat-${index}`"
              class="game-result-kv__row"
            >
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="rewards.length" class="game-result-section game-result-section--rewards">
          <h3 class="game-result-section__label">奖励</h3>
          <dl class="game-result-kv">
            <div
              v-for="(item, index) in rewards"
              :key="`reward-${index}`"
              class="game-result-kv__row game-result-kv__row--accent"
            >
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </section>

        <section
          v-if="highlights.length"
          class="game-result-section game-result-section--highlights"
        >
          <h3 class="game-result-section__label">亮点</h3>
          <dl class="game-result-kv">
            <div
              v-for="(item, index) in highlights"
              :key="`highlight-${index}`"
              class="game-result-kv__row"
            >
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </section>
      </section>

    </div>
    <template v-if="actions.length" #footer>
        <button
          v-for="action in actions"
          :key="action.key"
          type="button"
          class="game-result-action"
          :class="actionButtonClass(action)"
          :disabled="!!action.disabled"
          @click="handleAction(action)"
        >
          {{ action.label }}
        </button>
    </template>
  </AppModal>
</template>
<script setup>
import AppModal from '../../AppModal.vue';

defineProps({
  visible: { type: Boolean, required: true },
  title: { type: String, default: '本局结算' },
  subtitle: { type: String, default: '' },
  resultType: {
    type: String,
    default: 'neutral',
    validator: (value) => ['success', 'failed', 'neutral', 'record'].includes(value)
  },
  stats: { type: Array, default: () => [] },
  rewards: { type: Array, default: () => [] },
  highlights: { type: Array, default: () => [] },
  actions: { type: Array, default: () => [] }
});

const emit = defineEmits(['action', 'close']);


/**
 * @param {{ type?: string }} action
 * @returns {string}
 */
function actionButtonClass(action) {
  if (action.type === 'primary') {
    return 'game-action-btn--primary';
  }
  if (action.type === 'danger') {
    return 'game-action-btn--danger';
  }
  return 'game-action-btn--secondary';
}

/**
 * @param {{ key: string; disabled?: boolean }} action
 */
function handleAction(action) {
  if (action.disabled) {
    return;
  }
  emit('action', action.key);
  if (action.key === 'close') {
    emit('close');
  }
}

</script>
