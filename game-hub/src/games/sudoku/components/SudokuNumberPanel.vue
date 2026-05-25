<template>
  <div class="sudoku-number-panel" aria-label="剩余可用数字">
    <div
      v-for="n in 9"
      :key="n"
      class="sudoku-number-panel__item"
      :class="{ 'sudoku-number-panel__item--empty': (remaining[n] ?? 0) <= 0 }"
    >
      <span class="sudoku-number-panel__digit">{{ n }}</span>
      <span class="sudoku-number-panel__count">×{{ remaining[n] ?? 0 }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  /** @type {import('vue').PropType<Record<number, number>>} */
  remaining: {
    type: Object,
    required: true
  }
});
</script>
