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
defineProps({
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
