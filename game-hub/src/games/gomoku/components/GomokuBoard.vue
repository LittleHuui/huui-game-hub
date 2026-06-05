<template>
  <div class="gomoku-board" :style="boardStyle">
    <button
      v-for="cell in cells"
      :key="cell.key"
      type="button"
      class="gomoku-board__intersection"
      :class="cell.classList"
      :disabled="cell.disabled"
      :aria-label="cell.label"
      @click="onCellClick(cell.row, cell.col)"
      @mouseenter="onCellHover(cell.row, cell.col)"
      @mouseleave="onCellHover(null, null)"
    >
      <span
        v-if="cell.stone"
        class="gomoku-board__stone gomoku-board__stone--placed"
        :class="[cell.stoneClass, { 'gomoku-board__stone--last': cell.isLast }]"
      />
      <span
        v-else-if="cell.showPreview"
        class="gomoku-board__stone gomoku-board__stone--preview"
        :class="previewStoneClass"
      />
    </button>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  board: {
    type: Array,
    default: () => []
  },
  boardSize: {
    type: Number,
    default: 15
  },
  lastPlaceRow: {
    type: Number,
    default: null
  },
  lastPlaceCol: {
    type: Number,
    default: null
  },
  currentStone: {
    type: String,
    default: 'BLACK'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  interactive: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['cell-click']);

const hoverCell = ref(null);

const boardStyle = computed(() => ({
  '--gomoku-size': String(props.boardSize || 15)
}));

const previewStoneClass = computed(() => {
  const stone = String(props.currentStone || 'BLACK').toUpperCase();
  return stone === 'WHITE' ? 'gomoku-board__stone--white' : 'gomoku-board__stone--black';
});

const lastMoveCoords = computed(() => {
  const row = props.lastPlaceRow;
  const col = props.lastPlaceCol;
  if (row == null || col == null) {
    return null;
  }
  return { row: Number(row), col: Number(col) };
});

const cells = computed(() => {
  const size = Number(props.boardSize) || 15;
  const matrix = Array.isArray(props.board) ? props.board : [];
  const last = lastMoveCoords.value;
  const list = [];
  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      const stone = matrix[row]?.[col] ?? null;
      const isLast =
        last != null && Number(last.row) === row && Number(last.col) === col && stone != null;
      const isHover =
        hoverCell.value != null &&
        hoverCell.value.row === row &&
        hoverCell.value.col === col;
      const showPreview = !stone && props.interactive && !props.disabled && isHover;
      list.push({
        key: `${row}-${col}`,
        row,
        col,
        stone,
        isLast,
        stoneClass:
          stone === 'WHITE'
            ? 'gomoku-board__stone--white'
            : stone === 'BLACK'
              ? 'gomoku-board__stone--black'
              : '',
        showPreview,
        disabled: props.disabled || !props.interactive || stone != null,
        classList: {
          'gomoku-board__intersection--empty': stone == null
        },
        label: stone ? `${stone} ${row + 1},${col + 1}` : `空 ${row + 1},${col + 1}`
      });
    }
  }
  return list;
});

/**
 * @param {number} row
 * @param {number} col
 */
function onCellClick(row, col) {
  if (props.disabled || !props.interactive) {
    return;
  }
  emit('cell-click', row, col);
}

/**
 * @param {number|null} row
 * @param {number|null} col
 */
function onCellHover(row, col) {
  if (props.disabled || !props.interactive) {
    hoverCell.value = null;
    return;
  }
  if (row == null || col == null) {
    hoverCell.value = null;
    return;
  }
  hoverCell.value = { row, col };
}
</script>
