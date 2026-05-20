<template>
  <div
    class="game-stat-grid"
    :class="{ 'game-stat-grid--compact': compact }"
    :style="[themeVars, gridStyle]"
  >
    <slot />
  </div>
</template>

<script setup>
import { computed, inject, toRef } from 'vue';
import { GAME_STAT_THEME_KEY, provideGameStatTheme } from '../../composables/useGameStatTheme.js';

const props = defineProps({
  columns: { type: Number, default: 0 },
  minColumnWidth: { type: String, default: '84px' },
  compact: { type: Boolean, default: true },
  /** 无父级 GameHudStats 时生效：0–9 | 主题名 | random */
  themeSeed: { type: [Number, String], default: 'random' }
});

const parentTheme = inject(GAME_STAT_THEME_KEY, null);
const { themeVars } = parentTheme
  ? { themeVars: parentTheme.themeVars }
  : provideGameStatTheme(toRef(props, 'themeSeed'));

const gridStyle = computed(() => {
  if (props.columns > 0) {
    return { gridTemplateColumns: `repeat(${props.columns}, minmax(0, 1fr))` };
  }
  return { gridTemplateColumns: `repeat(auto-fit, minmax(${props.minColumnWidth}, 1fr))` };
});
</script>
