<template>
  <div class="game-number-input">
    <button
      type="button"
      class="game-number-input__btn game-number-input__btn--minus"
      :disabled="disabled || isMin"
      aria-label="减少"
      @click="handleStep(-1)"
    >
      −
    </button>
    <input
      :id="inputId"
      class="game-number-input__field"
      type="text"
      inputmode="numeric"
      autocomplete="off"
      :placeholder="placeholder"
      :value="displayValue"
      :disabled="disabled"
      @input="handleInput"
      @blur="handleBlur"
    />
    <button
      type="button"
      class="game-number-input__btn game-number-input__btn--plus"
      :disabled="disabled || isMax"
      aria-label="增加"
      @click="handleStep(1)"
    >
      +
    </button>
  </div>
</template>

<script setup>
import { computed, ref, toRef, watchEffect } from 'vue';

const props = defineProps({
  modelValue: {
    type: [Number, String],
    default: ''
  },
  min: {
    type: Number,
    default: Number.NEGATIVE_INFINITY
  },
  max: {
    type: Number,
    default: Number.POSITIVE_INFINITY
  },
  step: {
    type: Number,
    default: 1
  },
  disabled: {
    type: Boolean,
    default: false
  },
  placeholder: {
    type: String,
    default: ''
  },
  inputId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue', 'change']);

const internalValue = ref('');

const numericValue = computed(() => {
  const value = String(internalValue.value).trim();
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return parsed;
});

const displayValue = computed(() => internalValue.value);

const isMin = computed(() => {
  const value = numericValue.value;
  if (value === null) {
    return false;
  }
  return value <= props.min;
});

const isMax = computed(() => {
  const value = numericValue.value;
  if (value === null) {
    return false;
  }
  return value >= props.max;
});

watchEffect(() => {
  const external = toRef(props, 'modelValue').value;
  const value =
    external === null || typeof external === 'undefined'
      ? ''
      : String(external);
  internalValue.value = value;
});

function clamp(value) {
  let next = value;
  if (next === null) {
    return null;
  }
  if (Number.isFinite(props.min)) {
    next = Math.max(next, props.min);
  }
  if (Number.isFinite(props.max)) {
    next = Math.min(next, props.max);
  }
  return next;
}

function emitValue(value) {
  const next = clamp(value);
  if (next === null) {
    internalValue.value = '';
    emit('update:modelValue', null);
    emit('change', null);
    return;
  }
  internalValue.value = String(next);
  emit('update:modelValue', next);
  emit('change', next);
}

function handleInput(event) {
  internalValue.value = event.target.value;
}

function handleBlur() {
  const value = numericValue.value;
  if (value === null) {
    internalValue.value = '';
    emit('update:modelValue', null);
    emit('change', null);
    return;
  }
  emitValue(value);
}

function handleStep(direction) {
  if (props.disabled) {
    return;
  }
  const current = numericValue.value ?? 0;
  const step = Number.isFinite(props.step) && props.step > 0 ? props.step : 1;
  const next = current + direction * step;
  emitValue(next);
}
</script>

