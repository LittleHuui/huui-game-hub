<template>
  <div class="gomoku-board" :style="boardStyle">
    <svg class="gomoku-board__grid" :viewBox="`0 0 ${geometry.size} ${geometry.size}`" aria-hidden="true">
      <template v-for="(coordinate, index) in geometry.coordinates" :key="index">
        <line :x1="geometry.first" :y1="coordinate" :x2="geometry.last" :y2="coordinate" />
        <line :x1="coordinate" :y1="geometry.first" :x2="coordinate" :y2="geometry.last" />
      </template>
      <circle v-for="star in starPoints" :key="star.key" :cx="star.x" :cy="star.y" r="3" />
    </svg>
    <button
      v-for="cell in cells"
      :key="cell.key"
      type="button"
      class="gomoku-board__intersection"
      :class="cell.classList"
      :style="cell.position"
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

const geometry = computed(() => {
  const count = Math.max(2, Number(props.boardSize) || 15);
  const size = 480;
  const step = size / count;
  const first = step / 2;
  return { size, step, first, last: size - first, coordinates: Array.from({ length: count }, (_, i) => first + i * step) };
});
const boardStyle = computed(() => ({ '--gomoku-hit-size': `${100 / geometry.value.coordinates.length}%` }));
const starPoints = computed(() => {
  const coordinates = geometry.value.coordinates;
  if (coordinates.length !== 15) return [];
  return [[3, 3], [3, 11], [7, 7], [11, 3], [11, 11]].map(([row, col]) => ({ key: `${row}-${col}`, x: coordinates[col], y: coordinates[row] }));
});

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
        position: { left: `${geometry.value.coordinates[col] / geometry.value.size * 100}%`, top: `${geometry.value.coordinates[row] / geometry.value.size * 100}%` },
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
