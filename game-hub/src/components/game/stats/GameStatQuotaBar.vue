<template>
  <div v-if="items.length" class="game-stat-quota-bar">
    <span
      v-for="(item, index) in items"
      :key="item.label"
      class="game-stat-quota-bar__item"
      :style="itemThemeVars(item, index)"
    >
      <span class="game-stat-quota-bar__label">{{ item.label }}</span>
      <span class="game-stat-quota-bar__val">{{ item.used }}/{{ item.max }}</span>
    </span>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue';
import {
  GAME_STAT_THEME_COUNT,
  gameStatThemeVars,
  resolveGameStatThemeIndex
} from '../../../constants/gameStatThemes.js';
import { GAME_STAT_THEME_KEY, useGameStatThemeSlot } from '../../../composables/useGameStatTheme.js';

defineProps({
  items: { type: Array, default: () => [] },
  themeSeed: { type: [Number, String], default: undefined }
});

useGameStatThemeSlot();
const parentTheme = inject(GAME_STAT_THEME_KEY, null);
const baseThemeIndex = computed(() => parentTheme?.themeIndex?.value ?? 0);

/**
 * 各道具配额项使用不同主题色，避免与统计卡同色。
 * @param {{ themeSeed?: number|string }} item
 * @param {number} index
 */
function itemThemeVars(item, index) {
  const seed = item.themeSeed ?? (baseThemeIndex.value + 5 + index) % GAME_STAT_THEME_COUNT;
  return gameStatThemeVars(resolveGameStatThemeIndex(seed));
}
</script>
