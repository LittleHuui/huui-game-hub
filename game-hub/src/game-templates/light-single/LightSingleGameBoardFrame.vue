<template>
  <section class="game-card light-single-board-frame">
    <header v-if="title || subtitle" class="light-single-board-frame__head">
      <h2 v-if="title" class="light-single-board-frame__title">{{ title }}</h2>
      <p v-if="subtitle" class="light-single-board-frame__subtitle">{{ subtitle }}</p>
    </header>
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
  subtitle: {
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
