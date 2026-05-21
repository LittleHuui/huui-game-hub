<template>
  <div
    v-if="visible"
    class="game-result-mask"
    role="presentation"
    @click.self="handleMaskClick"
  >
    <div
      class="game-result-card"
      :class="resultTypeClass"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
    >
      <header class="game-result-header">
        <div class="game-result-header__badge" aria-hidden="true" />
        <div class="game-result-header__text">
          <h2 :id="titleId" class="game-result-title">{{ title }}</h2>
          <p v-if="subtitle" class="game-result-subtitle">{{ subtitle }}</p>
        </div>
      </header>

      <section v-if="stats.length" class="game-result-section">
        <h3 class="game-result-section__label">数据统计</h3>
        <dl class="game-result-kv">
          <div v-for="(item, index) in stats" :key="`stat-${index}`" class="game-result-kv__row">
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

      <section v-if="highlights.length" class="game-result-section game-result-section--highlights">
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

      <footer v-if="actions.length" class="game-result-actions">
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
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, useId } from 'vue';

const props = defineProps({
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

const titleId = useId();

const resultTypeClass = computed(() => `game-result-card--${props.resultType}`);

/**
 * @param {{ type?: string }} action
 * @returns {string}
 */
function actionButtonClass(action) {
  if (action.type === 'primary') {
    return 'game-result-action--primary';
  }
  if (action.type === 'danger') {
    return 'game-result-action--danger';
  }
  return 'game-result-action--secondary';
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

function handleMaskClick() {
  emit('close');
}
</script>

<style scoped>
.game-result-mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(4px);
}

.game-result-card {
  width: min(440px, 100%);
  max-height: min(90vh, 720px);
  overflow: auto;
  padding: 24px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: linear-gradient(165deg, rgba(17, 24, 39, 0.98), rgba(15, 23, 42, 0.96));
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
}

.game-result-card--success {
  border-color: rgba(16, 185, 129, 0.35);
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(16, 185, 129, 0.2);
}

.game-result-card--failed {
  border-color: rgba(239, 68, 68, 0.35);
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(239, 68, 68, 0.15);
}

.game-result-card--record {
  border-color: rgba(245, 158, 11, 0.4);
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(245, 158, 11, 0.2);
}

.game-result-card--neutral {
  border-color: rgba(148, 163, 184, 0.28);
}

.game-result-header {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.game-result-header__badge {
  flex-shrink: 0;
  width: 10px;
  height: 48px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.55);
}

.game-result-card--success .game-result-header__badge {
  background: linear-gradient(180deg, #34d399, #059669);
}

.game-result-card--failed .game-result-header__badge {
  background: linear-gradient(180deg, #f87171, #dc2626);
}

.game-result-card--record .game-result-header__badge {
  background: linear-gradient(180deg, #fbbf24, #d97706);
}

.game-result-card--neutral .game-result-header__badge {
  background: linear-gradient(180deg, #94a3b8, #64748b);
}

.game-result-header__text {
  min-width: 0;
  flex: 1;
}

.game-result-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.game-result-subtitle {
  margin: 8px 0 0;
  font-size: 0.92rem;
  line-height: 1.45;
  color: rgba(226, 232, 240, 0.82);
}

.game-result-section {
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.game-result-section--rewards {
  background: rgba(16, 185, 129, 0.08);
  border-color: rgba(16, 185, 129, 0.18);
}

.game-result-section--highlights {
  background: rgba(59, 130, 246, 0.08);
  border-color: rgba(59, 130, 246, 0.16);
}

.game-result-section__label {
  margin: 0 0 10px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(148, 163, 184, 0.95);
}

.game-result-kv {
  margin: 0;
}

.game-result-kv__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding: 7px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.game-result-kv__row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.game-result-kv__row dt {
  margin: 0;
  font-size: 0.9rem;
  color: rgba(203, 213, 225, 0.9);
}

.game-result-kv__row dd {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: #f8fafc;
  text-align: right;
}

.game-result-kv__row--accent dd {
  color: #6ee7b7;
}

.game-result-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  padding-top: 4px;
}

.game-result-action {
  min-width: 96px;
  padding: 10px 18px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-size: 0.92rem;
  font-weight: 600;
  transform: none;
}

.game-result-action:hover:not(:disabled) {
  transform: translateY(-1px);
}

.game-result-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
}

.game-result-action--primary {
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
}

.game-result-action--primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #34d399, #059669);
}

.game-result-action--secondary {
  background: rgba(30, 41, 59, 0.9);
  border-color: rgba(148, 163, 184, 0.35);
  color: #e2e8f0;
}

.game-result-action--secondary:hover:not(:disabled) {
  background: rgba(51, 65, 85, 0.95);
}

.game-result-action--danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: #fff;
}

@media (max-width: 480px) {
  .game-result-card {
    padding: 20px 18px;
  }

  .game-result-actions {
    width: 100%;
  }

  .game-result-action {
    flex: 1 1 auto;
    min-width: 0;
  }
}
</style>
