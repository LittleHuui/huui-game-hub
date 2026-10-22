<template>
  <div class="match3-board-host">
    <div
      ref="boardElement"
      class="match3-board"
      :style="{
        gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
        gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
        aspectRatio: `${cols} / ${rows}`
      }"
    >
      <button
        v-for="cell in flatCells"
        :key="cell.id"
        type="button"
        class="match3-cell"
        :class="cellClass(cell)"
        :style="cellStyle(cell)"
        :aria-label="`${itemMap[cell.type]?.name || cell.type}，第 ${cell.row + 1} 行第 ${cell.col + 1} 列`"
        @pointerdown="onPointerDown($event, cell)"
      >
        <span class="match3-cell-icon" :data-shape="items.findIndex((item) => item.itemCode === cell.type) % 6" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

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
const boardElement = ref(null);
const renderedWidth = ref(0);
const renderedHeight = ref(0);
let resizeObserver = null;
onMounted(() => {
  resizeObserver = new ResizeObserver(([entry]) => {
    renderedWidth.value = entry.contentRect.width;
    renderedHeight.value = entry.contentRect.height;
  });
  resizeObserver.observe(boardElement.value);
});
const visualScaleX = computed(() => renderedWidth.value > 0 && cols.value ? (renderedWidth.value + 6) / (cols.value * (props.cellSize + 6)) : 1);
const visualScaleY = computed(() => renderedHeight.value > 0 && rows.value ? (renderedHeight.value + 6) / (rows.value * (props.cellSize + 6)) : 1);

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
  const tx = (visual.translateX || 0) * visualScaleX.value;
  const ty = (visual.translateY || 0) * visualScaleY.value;
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
    width: '100%',
    height: '100%',
    background: `color-mix(in srgb, ${item.color || '#64748b'} 15%, white)`,
    color: item.color || '#64748b',
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
  resizeObserver?.disconnect();
  clearDrag();
});
</script>
