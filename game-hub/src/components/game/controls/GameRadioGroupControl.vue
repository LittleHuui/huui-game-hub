<template>
  <div
    class="game-radio-group-control"
    :class="[extraClass, { 'game-radio-group-control--disabled': disabled }]"
    role="radiogroup"
    :aria-disabled="disabled || undefined"
  >
    <label
      v-for="opt in options"
      :key="String(opt.value)"
      class="game-radio-group-control__option"
      :class="{ 'game-radio-group-control__option--active': isActive(opt.value) }"
    >
      <input
        type="radio"
        :name="groupName"
        :value="opt.value"
        :checked="isActive(opt.value)"
        :disabled="disabled"
        @change="onSelect(opt.value)"
      />
      <span>{{ opt.label }}</span>
    </label>
  </div>
</template>

<script setup>
import { computed, useId } from 'vue';

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
  name: {
    type: String,
    default: ''
  },
  extraClass: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue', 'change']);

const autoId = useId();
const groupName = computed(() => props.name || `game-radio-${autoId}`);

/**
 * @param {string|number|boolean} value
 * @returns {boolean}
 */
function isActive(value) {
  return String(props.modelValue) === String(value);
}

/**
 * @param {string|number|boolean} value
 */
function onSelect(value) {
  emit('update:modelValue', value);
  emit('change', value);
}
</script>
