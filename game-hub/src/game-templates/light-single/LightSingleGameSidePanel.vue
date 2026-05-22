<template>
  <GameControlPanel
    class="light-single-side-panel"
    :title="gameTitle"
    :subtitle="gameSubtitle"
    :description="gameDescription"
    :status-text="gameStatusText"
    :info-stats="infoStats"
    :fields="fields"
    :actions="actionItems"
    @field-change="$emit('field-change', $event)"
    @action="$emit('action', $event)"
  >
    <template v-if="$slots['title-extra']" #title-extra>
      <slot name="title-extra" />
    </template>
    <template #extra>
      <slot name="game-info-extra" />
    </template>
    <template
      v-for="field in customFields"
      :key="field.key"
      #[`field-${field.key}`]="slotProps"
    >
      <slot :name="`field-${field.key}`" v-bind="slotProps" />
    </template>
  </GameControlPanel>
</template>

<script setup>
import { computed } from 'vue';
import { GameControlPanel, GAME_CONTROL_TYPE } from '../../components/game/index.js';

const props = defineProps({
  gameTitle: {
    type: String,
    default: ''
  },
  gameSubtitle: {
    type: String,
    default: ''
  },
  gameDescription: {
    type: String,
    default: ''
  },
  gameStatusText: {
    type: String,
    default: ''
  },
  /** @type {import('vue').PropType<Array<{ label: string; value: string|number; key?: string }>>} */
  infoStats: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<Array<{ key: string; type?: string; label?: string; value?: unknown; options?: Array; disabled?: boolean }>>} */
  fields: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<Array<{ key: string; label: string; type?: string; size?: string; visible?: boolean; disabled?: boolean }>>} */
  actionItems: {
    type: Array,
    default: () => []
  }
});

defineEmits(['action', 'field-change']);

/** custom 类型字段，用于向 GameControlPanel 透传具名 slot */
const customFields = computed(() =>
  (props.fields || []).filter((f) => f?.type === GAME_CONTROL_TYPE.CUSTOM)
);
</script>
