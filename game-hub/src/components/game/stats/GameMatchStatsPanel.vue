<template>
  <GameHudStats :theme-seed="themeSeed">
    <GameStatGrid :compact="compact" :columns="columns" :min-column-width="minColumnWidth">
      <GameStatCard
        v-for="(stat, index) in stats"
        :key="stat.key || stat.label || index"
        :label="stat.label"
        :value="stat.value"
        :helper="stat.helper || ''"
        :icon="stat.icon || ''"
        :tone="resolveTone(stat.tone)"
        layout="inline"
      />
    </GameStatGrid>
    <GameStatQuotaBar v-if="quotas.length > 0" :items="quotas" />
    <p v-if="message" class="game-hud-stats__message">{{ message }}</p>
  </GameHudStats>
</template>

<script setup>
import { GAME_STAT_TONE } from '../controls/gameControlEnums.js';
import GameHudStats from './GameHudStats.vue';
import GameStatGrid from './GameStatGrid.vue';
import GameStatCard from './GameStatCard.vue';
import GameStatQuotaBar from './GameStatQuotaBar.vue';

defineProps({
  /** @type {import('vue').PropType<Array<{ key?: string; label: string; value: string|number; tone?: string; icon?: string; helper?: string }>>} */
  stats: {
    type: Array,
    default: () => []
  },
  quotas: {
    type: Array,
    default: () => []
  },
  message: {
    type: String,
    default: ''
  },
  themeSeed: {
    type: [Number, String],
    default: 'random'
  },
  columns: {
    type: Number,
    default: 0
  },
  minColumnWidth: {
    type: String,
    default: '84px'
  },
  compact: {
    type: Boolean,
    default: true
  }
});

/**
 * 将业务传入的 tone 归一化为 GameStatCard 支持的枚举值。
 * @param {string} [tone]
 * @returns {string}
 */
function resolveTone(tone) {
  if (tone && Object.values(GAME_STAT_TONE).includes(tone)) {
    return tone;
  }
  return GAME_STAT_TONE.NEUTRAL;
}
</script>
