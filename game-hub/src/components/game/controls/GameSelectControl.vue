<template>
  <div class="game-select-control" :class="extraClass">
    <select
      :id="inputId || undefined"
      :value="modelValue"
      :disabled="disabled"
      @change="onChange"
    >
      <option v-for="opt in options" :key="String(opt.value)" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  modelValue: {
    type: [String, Number, Boolean],
    default: ''
  },
  options: {
    type: Array,
    default: () => []
  },
  disabled: {
    type: Boolean,
    default: false
  },
  inputId: {
    type: String,
    default: ''
  },
  extraClass: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue', 'change']);

const inputId = computed(() => props.inputId || undefined);

/**
 * @param {Event} event
 */
function onChange(event) {
  const value = event.target?.value;
  emit('update:modelValue', value);
  emit('change', value);
}
</script>
