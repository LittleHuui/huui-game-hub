<template>
  <div class="game-hud-stats">
    <slot />
  </div>
</template>

<script setup>
import { toRef } from 'vue';
import { provideGameStatTheme } from '../../../composables/useGameStatTheme.js';

const props = defineProps({
  /** 0–9 | 主题名（如 emerald）| random */
  themeSeed: {
    type: [Number, String],
    default: 'random'
  }
});

provideGameStatTheme(toRef(props, 'themeSeed'));
</script>
