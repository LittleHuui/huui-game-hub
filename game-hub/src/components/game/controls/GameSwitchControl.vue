<template>
  <div class="game-switch-control" :class="extraClass">
    <span v-if="label" class="game-switch-control__text">{{ label }}</span>
    <button
      type="button"
      class="game-switch-control__track"
      :class="{ 'game-switch-control__track--on': modelValue }"
      role="switch"
      :aria-checked="modelValue"
      :disabled="disabled"
      @click="toggle"
    >
      <span class="game-switch-control__thumb" aria-hidden="true" />
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  label: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  extraClass: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue', 'change']);

/**
 * 切换开关状态。
 */
function toggle() {
  if (props.disabled) {
    return;
  }
  const next = !props.modelValue;
  emit('update:modelValue', next);
  emit('change', next);
}
</script>
