<template>
  <div class="game-stat-card" :class="[layoutClass, toneClass]" :style="themeVars">
    <div class="game-stat-card__main">
      <span class="game-stat-card__label">
        <span v-if="icon" class="game-stat-card__icon-inline" aria-hidden="true">{{ icon }}</span>
        {{ label }}<template v-if="helper && layout === 'inline'"><span class="game-stat-card__helper-inline"> · {{ helper }}</span></template>
      </span>
      <span class="game-stat-card__value">{{ value }}</span>
    </div>
    <span v-if="helper && layout !== 'inline'" class="game-stat-card__helper">{{ helper }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useGameStatTheme, useGameStatThemeSlot } from '../../../composables/useGameStatTheme.js';
import { GAME_STAT_TONE } from '../controls/gameControlEnums.js';

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  helper: { type: String, default: '' },
  icon: { type: String, default: '' },
  layout: {
    type: String,
    default: 'inline',
    validator: (v) => ['inline', 'stack'].includes(v)
  },
  tone: {
    type: String,
    default: 'neutral',
    validator: (v) => Object.values(GAME_STAT_TONE).includes(v) || v === 'default'
  },
  themeSeed: { type: [Number, String], default: undefined },
  themeOffset: { type: Number, default: 0 }
});

useGameStatThemeSlot();
const { themeVars } = useGameStatTheme(props.themeSeed, props.themeOffset);
const layoutClass = computed(() => `game-stat-card--${props.layout}`);
const toneClass = computed(() => {
  const resolved = props.tone === 'default' ? GAME_STAT_TONE.NEUTRAL : props.tone;
  return `game-stat-card--${resolved}`;
});
</script>
