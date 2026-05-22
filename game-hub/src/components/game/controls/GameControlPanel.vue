<template>
  <section class="game-card game-control-panel">
    <header v-if="title || $slots['title-extra']" class="game-control-panel__header">
      <h2 v-if="title" class="game-card__title">{{ title }}</h2>
      <slot name="title-extra" />
    </header>
    <div class="game-card__body">
      <p v-if="subtitle" class="game-control-panel__subtitle">{{ subtitle }}</p>
      <p v-if="description" class="game-control-panel__description">{{ description }}</p>
      <p v-if="statusText" class="game-control-panel__status">{{ statusText }}</p>

      <div v-if="infoStats.length > 0" class="game-control-panel__info-stats">
        <div
          v-for="(stat, index) in infoStats"
          :key="stat.key || stat.label || index"
          class="game-control-panel__info-stat"
        >
          <span class="game-control-panel__info-stat-label">{{ stat.label }}</span>
          <span class="game-control-panel__info-stat-value">{{ stat.value }}</span>
        </div>
      </div>

      <slot name="extra" />

      <div v-if="fields.length > 0" class="game-control-panel__fields">
        <GameControlField
          v-for="field in fields"
          :key="field.key"
          :field="field"
          @change="onFieldChange"
        >
          <template v-if="field.type === GAME_CONTROL_TYPE.CUSTOM">
            <slot :name="`field-${field.key}`" :field="field" />
          </template>
        </GameControlField>
      </div>

      <GameActionBar v-if="actions.length > 0" :actions="actions" @action="onAction" />
    </div>
  </section>
</template>

<script setup>
import { GAME_CONTROL_TYPE } from './gameControlEnums.js';
import GameControlField from './GameControlField.vue';
import GameActionBar from './GameActionBar.vue';

defineProps({
  title: {
    type: String,
    default: ''
  },
  subtitle: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  },
  statusText: {
    type: String,
    default: ''
  },
  /** @type {import('vue').PropType<Array<{ key?: string; label: string; value: string|number }>>} */
  infoStats: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<Array<{ key: string; type: string; label?: string; value?: unknown; options?: Array; disabled?: boolean }>>} */
  fields: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<Array<{ key: string; label: string; type?: string; size?: string; visible?: boolean; disabled?: boolean }>>} */
  actions: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['field-change', 'action']);

/**
 * @param {{ key: string; value: unknown }} payload
 */
function onFieldChange(payload) {
  emit('field-change', payload);
}

/**
 * @param {string} key
 */
function onAction(key) {
  emit('action', key);
}
</script>
