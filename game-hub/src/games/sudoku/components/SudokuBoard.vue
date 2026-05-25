<template>
  <div ref="wrapRef" class="sudoku-wrap">
    <div ref="boardRef" class="sudoku-board">
      <div class="sudoku-board__grid">
        <SudokuCell
          v-for="cell in flatCells"
          :key="`${cell.row}-${cell.col}`"
          :cell="cell"
          :selected="isSelected(cell)"
          :peer-highlight="isPeerHighlight(cell)"
          :disabled="interactionDisabled"
          @select="onCellSelect"
          @erase-cell="onCellErase"
        />
      </div>
      <div class="sudoku-board__box-lines" aria-hidden="true">
        <span class="sudoku-board__box-line sudoku-board__box-line--vertical sudoku-board__box-line--first"></span>
        <span class="sudoku-board__box-line sudoku-board__box-line--vertical sudoku-board__box-line--second"></span>
        <span class="sudoku-board__box-line sudoku-board__box-line--horizontal sudoku-board__box-line--first"></span>
        <span class="sudoku-board__box-line sudoku-board__box-line--horizontal sudoku-board__box-line--second"></span>
      </div>
      <SudokuNumberPopup
        :visible="popupVisible"
        :position="popupPosition"
        :placement="popupPlacement"
        :available-numbers="availableNumbers"
        @pick="onPopupPick"
        @close="$emit('close-popup')"
      />
    </div>

    <label class="sudoku-draft-toggle">
      <input
        type="checkbox"
        :checked="draftMode"
        :disabled="draftToggleDisabled"
        @change="$emit('update:draftMode', $event.target.checked)"
      />
      草稿模式
    </label>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import SudokuCell from './SudokuCell.vue';
import SudokuNumberPopup from './SudokuNumberPopup.vue';

const props = defineProps({
  /** @type {import('vue').PropType<import('../sudokuEngine.js').SudokuCell[][]>} */
  cells: {
    type: Array,
    required: true
  },
  selectedRow: {
    type: Number,
    default: -1
  },
  selectedCol: {
    type: Number,
    default: -1
  },
  draftMode: {
    type: Boolean,
    default: false
  },
  draftToggleDisabled: {
    type: Boolean,
    default: false
  },
  interactionDisabled: {
    type: Boolean,
    default: false
  },
  popupVisible: {
    type: Boolean,
    default: false
  },
  popupPosition: {
    type: Object,
    default: null
  },
  popupPlacement: {
    type: String,
    default: 'bottom'
  },
  /** @type {import('vue').PropType<Record<number, boolean>>} */
  availableNumbers: {
    type: Object,
    default: () => ({})
  }
});

const emit = defineEmits([
  'select-cell',
  'erase-cell',
  'pick-number',
  'update:draftMode',
  'close-popup'
]);

const wrapRef = ref(null);
const boardRef = ref(null);

const flatCells = computed(() => {
  const list = [];
  for (const row of props.cells) {
    for (const cell of row) {
      list.push(cell);
    }
  }
  return list;
});

/**
 * @param {import('../sudokuEngine.js').SudokuCell} cell
 * @returns {boolean}
 */
function isSelected(cell) {
  return cell.row === props.selectedRow && cell.col === props.selectedCol;
}

/**
 * @param {import('../sudokuEngine.js').SudokuCell} cell
 * @returns {boolean}
 */
function isPeerHighlight(cell) {
  if (props.selectedRow < 0 || props.selectedCol < 0) {
    return false;
  }
  const sr = props.selectedRow;
  const sc = props.selectedCol;
  if (cell.row === sr && cell.col === sc) {
    return false;
  }
  if (cell.row === sr || cell.col === sc) {
    return true;
  }
  const boxR = Math.floor(sr / 3);
  const boxC = Math.floor(sc / 3);
  return Math.floor(cell.row / 3) === boxR && Math.floor(cell.col / 3) === boxC;
}

/**
 * @param {import('../sudokuEngine.js').SudokuCell} cell
 * @param {MouseEvent} event
 */
function onCellSelect(cell, event) {
  emit('select-cell', { row: cell.row, col: cell.col, cell, event });
}

/**
 * @param {import('../sudokuEngine.js').SudokuCell} cell
 * @param {MouseEvent} event
 */
function onCellErase(cell, event) {
  emit('erase-cell', { row: cell.row, col: cell.col, cell, event });
}

/**
 * @param {number} num
 */
function onPopupPick(num) {
  emit('pick-number', num);
}

defineExpose({ wrapRef, boardRef });
</script>
