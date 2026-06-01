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
      ref="inputRef"
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
const inputRef = ref(null);

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

<style scoped>
.game-number-input {
  display: inline-flex;
  align-items: stretch;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.8);
}

.game-number-input__field {
  flex: 1 1 auto;
  min-width: 0;
  padding: 8px 10px;
  border: none;
  border-radius: 0;
  outline: none;
  background: #f8fafc;
  color: #0f172a;
  font-size: 14px;
  text-align: center;
}

.game-number-input__field:disabled {
  background: rgba(226, 232, 240, 0.7);
  color: rgba(100, 116, 139, 0.9);
}

.game-number-input__btn {
  flex: 0 0 auto;
  width: 32px;
  padding: 0;
  border: none;
  border-radius: 0;
  outline: none;
  background: #f8fafc;
  color: #334155;
  font-size: 16px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.game-number-input__btn:hover:not(:disabled) {
  background: rgba(226, 232, 240, 0.95);
  color: #0f172a;
  transform: none;
}

.game-number-input__btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
}

.game-number-input__btn--minus {
  border-right: 1px solid rgba(148, 163, 184, 0.32);
}

.game-number-input__btn--plus {
  border-left: 1px solid rgba(148, 163, 184, 0.32);
}
</style>

