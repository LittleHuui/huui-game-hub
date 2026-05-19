<template>
  <div class="match3-board-wrap">
    <div
      class="match3-board"
      :style="{
        gridTemplateColumns: `repeat(${cols}, ${cellSize}px)`,
        gridTemplateRows: `repeat(${rows}, ${cellSize}px)`
      }"
    >
      <button
        v-for="cell in flatCells"
        :key="cell.id"
        type="button"
        class="match3-cell"
        :class="cellClass(cell)"
        :style="cellStyle(cell)"
        @pointerdown="onPointerDown($event, cell)"
      >
        <span v-if="itemMap[cell.type]?.icon" class="match3-cell-icon">{{ itemMap[cell.type].icon }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue';

const props = defineProps({
  board: { type: Array, required: true },
  items: { type: Array, required: true },
  activeTool: { type: String, default: '' },
  cellVisuals: { type: Object, default: () => ({}) },
  cellSize: { type: Number, default: 44 },
  inputLocked: { type: Boolean, default: false },
  swapMs: { type: Number, default: 180 },
  removeMs: { type: Number, default: 220 },
  dropMs: { type: Number, default: 260 }
});

const emit = defineEmits(['swap-request', 'cell-click']);

const dragState = ref(null);

const rows = computed(() => props.board.length);
const cols = computed(() => props.board[0]?.length || 0);
const flatCells = computed(() => props.board.flat().filter(Boolean));
const itemMap = computed(() => {
  const map = {};
  for (const item of props.items || []) {
    map[item.itemCode] = item;
  }
  return map;
});

const dragThreshold = computed(() => Math.max(12, props.cellSize * 0.22));

/**
 * @param {object} cell
 * @returns {object}
 */
function cellClass(cell) {
  const visual = props.cellVisuals[cell.id] || {};
  const dragging =
    dragState.value &&
    dragState.value.from.row === cell.row &&
    dragState.value.from.col === cell.col;
  return {
    'is-dragging': dragging,
    'is-bomb-target': props.activeTool === 'bomb',
    'is-removing': visual.effect === 'removing',
    'is-shuffling': visual.effect === 'shuffle'
  };
}

/**
 * @param {object} cell
 * @returns {string}
 */
function cellTransform(cell) {
  const visual = props.cellVisuals[cell.id];
  if (!visual) {
    return '';
  }
  const tx = visual.translateX || 0;
  const ty = visual.translateY || 0;
  if (tx === 0 && ty === 0) {
    return '';
  }
  return `translate3d(${tx}px, ${ty}px, 0)`;
}

/**
 * @param {object} cell
 * @returns {object}
 */
function cellStyle(cell) {
  const item = itemMap.value[cell.type] || {};
  const visual = props.cellVisuals[cell.id] || {};
  const transform = cellTransform(cell);
  const transitionMs =
    visual.effect === 'removing'
      ? props.removeMs
      : transform
        ? props.swapMs
        : props.dropMs;
  const style = {
    gridRowStart: cell.row + 1,
    gridColumnStart: cell.col + 1,
    width: `${props.cellSize}px`,
    height: `${props.cellSize}px`,
    background: item.color || '#64748b',
    '--match3-transition-ms': `${transitionMs}ms`
  };
  if (transform) {
    style.transform = transform;
  }
  return style;
}

/**
 * @param {PointerEvent} event
 * @param {object} cell
 */
function onPointerDown(event, cell) {
  if (props.inputLocked || !cell) {
    return;
  }
  if (props.activeTool === 'bomb') {
    emit('cell-click', cell);
    return;
  }
  event.preventDefault();
  dragState.value = {
    pointerId: event.pointerId,
    from: { row: cell.row, col: cell.col },
    startX: event.clientX,
    startY: event.clientY,
    triggered: false
  };
  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

/**
 * @param {PointerEvent} event
 */
function onPointerMove(event) {
  const state = dragState.value;
  if (!state || state.pointerId !== event.pointerId || state.triggered) {
    return;
  }

  const dx = event.clientX - state.startX;
  const dy = event.clientY - state.startY;
  const threshold = dragThreshold.value;

  if (Math.hypot(dx, dy) < threshold) {
    return;
  }

  let toRow = state.from.row;
  let toCol = state.from.col;

  if (Math.abs(dx) >= Math.abs(dy)) {
    toCol += dx > 0 ? 1 : -1;
  } else {
    toRow += dy > 0 ? 1 : -1;
  }

  state.triggered = true;

  if (toRow < 0 || toRow >= rows.value || toCol < 0 || toCol >= cols.value) {
    clearDrag();
    return;
  }

  emit('swap-request', { from: { ...state.from }, to: { row: toRow, col: toCol } });
  clearDrag();
}

/**
 * @param {PointerEvent} [event]
 */
function onPointerUp(event) {
  if (!dragState.value) {
    return;
  }
  if (!event || dragState.value.pointerId === event.pointerId) {
    clearDrag();
  }
}

/**
 * 清理拖动状态
 */
function clearDrag() {
  if (!dragState.value) {
    return;
  }
  window.removeEventListener('pointermove', onPointerMove);
  window.removeEventListener('pointerup', onPointerUp);
  window.removeEventListener('pointercancel', onPointerUp);
  dragState.value = null;
}

onBeforeUnmount(() => {
  clearDrag();
});
</script>

<style scoped>
.match3-board-wrap {
  padding: 18px;
  border-radius: 24px;
  background: rgba(15, 23, 42, 0.72);
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
  touch-action: none;
  user-select: none;
}

.match3-board {
  display: grid;
  gap: 6px;
}

.match3-cell {
  border: 2px solid rgba(255, 255, 255, 0.42);
  border-radius: 12px;
  cursor: grab;
  box-shadow:
    inset 0 2px 10px rgba(255, 255, 255, 0.42),
    inset 0 -8px 14px rgba(0, 0, 0, 0.18),
    0 4px 10px rgba(0, 0, 0, 0.22);
  transition:
    transform var(--match3-transition-ms, 180ms) ease,
    opacity var(--match3-transition-ms, 220ms) ease,
    box-shadow 160ms ease,
    filter 160ms ease;
  will-change: transform, opacity;
}

.match3-cell:active {
  cursor: grabbing;
}

.match3-cell.is-dragging {
  z-index: 2;
  transform: translateY(-3px) scale(1.08);
  box-shadow:
    0 0 0 3px rgba(255, 255, 255, 0.95),
    0 10px 22px rgba(0, 0, 0, 0.28),
    inset 0 2px 10px rgba(255, 255, 255, 0.5);
}

.match3-cell.is-bomb-target:hover {
  box-shadow:
    0 0 0 3px rgba(252, 165, 165, 0.95),
    0 0 24px rgba(248, 113, 113, 0.45),
    inset 0 2px 8px rgba(255, 255, 255, 0.35);
}

.match3-cell.is-removing {
  opacity: 0;
  transform: scale(0.2) rotate(12deg);
  pointer-events: none;
}

.match3-cell.is-shuffling {
  animation: match3Shuffle 380ms ease;
}

.match3-cell-icon {
  font-size: 22px;
}

@keyframes match3Shuffle {
  0% {
    transform: rotate(0deg) scale(1);
  }
  50% {
    transform: rotate(8deg) scale(0.86);
  }
  100% {
    transform: rotate(0deg) scale(1);
  }
}
</style>
