<template>
  <section class="light-single-board-frame" :aria-label="title || '棋盘'">
    <div class="light-single-board-frame__body">
      <slot />
      <GamePauseOverlay
        :visible="paused"
        :title="pauseTitle"
        :description="pauseDescription"
        :action-text="pauseActionText"
        @resume="$emit('resume')"
      />
    </div>
  </section>
</template>

<script setup>
import GamePauseOverlay from '../../components/game/panels/GamePauseOverlay.vue';

defineProps({
  title: {
    type: String,
    default: ''
  },
  paused: {
    type: Boolean,
    default: false
  },
  pauseTitle: {
    type: String,
    default: ''
  },
  pauseDescription: {
    type: String,
    default: ''
  },
  pauseActionText: {
    type: String,
    default: ''
  }
});

defineEmits(['resume']);
</script>
