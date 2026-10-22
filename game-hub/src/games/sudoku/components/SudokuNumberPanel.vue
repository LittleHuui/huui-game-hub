<template>
  <div class="sudoku-number-panel" aria-label="选择数字">
    <button v-for="n in 9" :key="n" type="button" class="sudoku-number-panel__item"
      :disabled="disabled || !availableNumbers[n]" :aria-label="`填入 ${n}，剩余 ${remaining[n] ?? 0} 个`" @click="$emit('pick', n)">
      <span class="sudoku-number-panel__digit">{{ n }}</span><span class="sudoku-number-panel__count">{{ remaining[n] ?? 0 }}</span>
    </button>
  </div>
</template>
<script setup>
defineProps({
  remaining: { type: Object, required: true }, availableNumbers: { type: Object, default: () => ({}) },
  disabled: { type: Boolean, default: false }
});
defineEmits(['pick']);
</script>
