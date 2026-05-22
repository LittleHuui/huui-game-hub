<template>
  <div
    v-if="visible"
    class="game-pause-overlay"
    role="presentation"
    @click.self="emitResume"
  >
    <div class="game-pause-overlay__panel" role="status" @click.stop>
      <h3 class="game-pause-overlay__title">{{ title }}</h3>
      <p v-if="description" class="game-pause-overlay__description">{{ description }}</p>
      <button
        type="button"
        class="side-action game-action-btn game-action-btn--resume game-action-btn--md game-pause-overlay__action"
        @click="emitResume"
      >
        {{ actionText }}
      </button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '游戏已暂停'
  },
  description: {
    type: String,
    default: '点击继续或点击遮罩恢复游戏'
  },
  actionText: {
    type: String,
    default: '继续游戏'
  }
});

const emit = defineEmits(['resume']);

/**
 * 通知业务页恢复对局。
 */
function emitResume() {
  emit('resume');
}
</script>

<style scoped>
.game-pause-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  border-radius: inherit;
  background: rgba(2, 6, 23, 0.62);
  backdrop-filter: blur(6px);
  cursor: pointer;
}

.game-pause-overlay__panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  max-width: min(360px, 100%);
  padding: 24px 28px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(15, 23, 42, 0.88);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35);
  cursor: default;
  text-align: center;
}

.game-pause-overlay__title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #f8fafc;
}

.game-pause-overlay__description {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: rgba(148, 163, 184, 0.95);
}

.game-pause-overlay__action {
  margin-top: 4px;
  width: auto;
}
</style>
