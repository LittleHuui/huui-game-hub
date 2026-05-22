<template>
  <div
    class="game-control-field"
    :class="{ 'game-control-field--disabled': field.disabled }"
  >
    <label v-if="field.label" class="game-control-field__label" :for="fieldId">
      {{ field.label }}
    </label>

    <GameSelectControl
      v-if="field.type === GAME_CONTROL_TYPE.SELECT"
      :id="fieldId"
      :input-id="fieldId"
      :model-value="field.value"
      :options="field.options || []"
      :disabled="field.disabled"
      @change="onValueChange"
    />

    <GameRadioGroupControl
      v-else-if="field.type === GAME_CONTROL_TYPE.RADIO"
      :model-value="field.value"
      :options="field.options || []"
      :disabled="field.disabled"
      :name="fieldId"
      @change="onValueChange"
    />

    <GameSwitchControl
      v-else-if="field.type === GAME_CONTROL_TYPE.SWITCH"
      :model-value="Boolean(field.value)"
      :disabled="field.disabled"
      @change="onValueChange"
    />

    <slot v-else-if="field.type === GAME_CONTROL_TYPE.CUSTOM" :field="field" />
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { GAME_CONTROL_TYPE } from './gameControlEnums.js';
import GameSelectControl from './GameSelectControl.vue';
import GameRadioGroupControl from './GameRadioGroupControl.vue';
import GameSwitchControl from './GameSwitchControl.vue';

const props = defineProps({
  /** @type {import('vue').PropType<{ key: string; type: string; label?: string; value?: unknown; options?: Array; disabled?: boolean }>} */
  field: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(['change']);

const fieldId = computed(() => `game-control-${props.field.key}`);

/**
 * @param {unknown} value
 */
function onValueChange(value) {
  emit('change', { key: props.field.key, value });
}
</script>
