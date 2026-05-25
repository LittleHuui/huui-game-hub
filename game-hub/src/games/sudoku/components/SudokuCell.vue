<template>
  <button
    type="button"
    class="sudoku-cell"
    :class="cellClasses"
    :disabled="disabled"
    :aria-label="ariaLabel"
    @click="$emit('select', cell, $event)"
    @contextmenu.prevent="handleContextMenu"
  >
    <span v-if="cell.value != null" class="sudoku-cell__value">{{ cell.value }}</span>
    <div v-else-if="showDrafts" class="sudoku-cell__drafts">
      <span
        v-for="n in 9"
        :key="n"
        class="sudoku-cell__draft"
      >{{ draftMap[n] || '' }}</span>
    </div>
  </button>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  /** @type {import('vue').PropType<import('../sudokuEngine.js').SudokuCell>} */
  cell: {
    type: Object,
    required: true
  },
  selected: {
    type: Boolean,
    default: false
  },
  peerHighlight: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['select', 'erase-cell']);

/**
 * @param {MouseEvent} event
 */
function handleContextMenu(event) {
  emit('erase-cell', props.cell, event);
}

const editable = computed(() => !props.cell.fixed);

const showDrafts = computed(
  () => props.cell.value == null && Array.isArray(props.cell.drafts) && props.cell.drafts.length > 0
);

const draftMap = computed(() => {
  const map = {};
  for (const n of props.cell.drafts || []) {
    map[n] = String(n);
  }
  return map;
});

const cellClasses = computed(() => {
  const c = props.cell;
  return {
    'sudoku-cell--fixed': c.fixed,
    'sudoku-cell--editable': !c.fixed,
    'sudoku-cell--selected': props.selected,
    'sudoku-cell--peer': props.peerHighlight && !props.selected,
    'sudoku-cell--conflict': c.conflict && !c.fixed,
    'sudoku-cell--value-fixed': c.fixed && c.value != null,
    'sudoku-cell--value-user': !c.fixed && c.value != null && !c.hinted,
    'sudoku-cell--value-hinted': !c.fixed && c.value != null && c.hinted
  };
});

const ariaLabel = computed(() => {
  const { row, col, value, fixed } = props.cell;
  const pos = `第 ${row + 1} 行第 ${col + 1} 列`;
  if (fixed) {
    return `${pos} 题目数字 ${value}`;
  }
  if (value != null) {
    return `${pos} 填入 ${value}`;
  }
  return `${pos} 空格`;
});
</script>
