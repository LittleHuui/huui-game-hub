<template>
  <div class="game2048-wrap">
    <div
      ref="boardRef"
      class="game2048-board"
      :style="boardStyle"
      tabindex="0"
      role="application"
      aria-label="2048 棋盘"
      @keydown.prevent="onKeydown"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @pointerleave="onPointerUp"
    >
      <div class="game2048-grid">
        <div
          v-for="cell in backgroundCells"
          :key="cell.key"
          class="game2048-cell"
          :class="{ 'is-targetable': selectMode && hasTileAt(cell.row, cell.col) }"
          @click="onCellClick(cell.row, cell.col)"
        />
      </div>
      <div ref="tileLayerRef" class="game2048-tile-layer">
        <div
          v-for="tile in renderTiles"
          :key="tile.id"
          class="game2048-tile"
          :class="[
            getTileClass(tile.value),
            fontSizeClass(tile.value),
            tileAnimClass(tile)
          ]"
          :style="tilePositionStyle(tile)"
        >
          {{ tile.value }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { directionFromDelta, directionFromKey } from '../game2048Engine.js';
import { getTileClass } from '../game2048TileStyle.js';

const TILE_LAYER_INSET_PX = 10;
const GRID_GAP_PX = 10;

const props = defineProps({
  tiles: {
    type: Array,
    required: true
  },
  boardSize: {
    type: Number,
    default: 4
  },
  selectMode: {
    type: Boolean,
    default: false
  },
  moveInputLocked: {
    type: Boolean,
    default: false
  },
  boardStyle: {
    type: Object,
    default: () => ({})
  },
  slideOffsets: {
    type: Object,
    default: () => ({})
  },
  newTileIds: {
    type: Object,
    default: () => ({})
  },
  mergedTileIds: {
    type: Object,
    default: () => ({})
  },
  clearingTileId: {
    type: Number,
    default: null
  }
});

const emit = defineEmits(['move', 'cell-select']);

const boardRef = ref(null);
const tileLayerRef = ref(null);
const pointerStart = ref(null);
const pointerId = ref(null);
const layerWidthPx = ref(0);

let resizeObserver = null;

const backgroundCells = computed(() => {
  const cells = [];
  const size = props.boardSize || 4;
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      cells.push({ key: `bg-${r}-${c}`, row: r, col: c });
    }
  }
  return cells;
});

const renderTiles = computed(() => {
  const seen = new Set();
  const list = [];
  for (const tile of props.tiles || []) {
    if (!tile || seen.has(tile.id)) {
      continue;
    }
    seen.add(tile.id);
    list.push(tile);
  }
  return list;
});

const cellSizePx = computed(() => {
  const size = props.boardSize || 4;
  const layer = layerWidthPx.value;
  if (layer <= 0) {
    return 0;
  }
  return (layer - GRID_GAP_PX * (size - 1)) / size;
});

const cellStridePx = computed(() => cellSizePx.value + GRID_GAP_PX);

/**
 * 测量 tile 层宽度以换算像素位移。
 */
function measureLayer() {
  const el = tileLayerRef.value;
  if (!el) {
    return;
  }
  layerWidthPx.value = el.clientWidth;
}

/**
 * @param {number} row
 * @param {number} col
 * @returns {boolean}
 */
function hasTileAt(row, col) {
  return (props.tiles || []).some((t) => t.row === row && t.col === col && t.value > 0);
}

/**
 * @param {number} value
 * @returns {string}
 */
function fontSizeClass(value) {
  const digits = String(value).length;
  if (digits <= 2) {
    return 'game2048-tile--sm';
  }
  if (digits <= 3) {
    return 'game2048-tile--md';
  }
  return 'game2048-tile--lg';
}

/**
 * @param {object} tile
 * @returns {string[]}
 */
function tileAnimClass(tile) {
  const classes = [];
  if (props.newTileIds[tile.id]) {
    classes.push('is-new');
  }
  if (props.mergedTileIds[tile.id]) {
    classes.push('is-merged');
  }
  if (props.clearingTileId === tile.id) {
    classes.push('is-clearing');
  }
  if (props.slideOffsets[tile.id]) {
    classes.push('is-sliding');
  }
  return classes;
}

/**
 * 绝对定位 + translate3d，仅滑动阶段过渡 transform。
 * @param {object} tile
 * @returns {Record<string, string>}
 */
function tilePositionStyle(tile) {
  const stride = cellStridePx.value;
  const cell = cellSizePx.value;
  if (stride <= 0 || cell <= 0) {
    return {};
  }
  const left = tile.col * stride;
  const top = tile.row * stride;
  const slide = props.slideOffsets[tile.id];
  const dx = slide?.dx ?? 0;
  const dy = slide?.dy ?? 0;
  const style = {
    width: `${cell}px`,
    height: `${cell}px`,
    left: `${left}px`,
    top: `${top}px`
  };
  if (dx !== 0 || dy !== 0) {
    style.transform = `translate3d(${dx}px, ${dy}px, 0)`;
  }
  return style;
}

/**
 * @param {KeyboardEvent} event
 */
function onKeydown(event) {
  if (props.moveInputLocked || props.selectMode) {
    return;
  }
  const direction = directionFromKey(event.key);
  if (!direction) {
    return;
  }
  emit('move', direction);
}

/**
 * @param {PointerEvent} event
 */
function onPointerDown(event) {
  if (props.moveInputLocked) {
    return;
  }
  boardRef.value?.focus({ preventScroll: true });
  pointerId.value = event.pointerId;
  pointerStart.value = { x: event.clientX, y: event.clientY };
  try {
    event.currentTarget?.setPointerCapture?.(event.pointerId);
  } catch {
    /* 部分环境不支持 capture */
  }
}

/**
 * @param {PointerEvent} event
 */
function onPointerMove(event) {
  if (pointerId.value !== event.pointerId || !pointerStart.value) {
    return;
  }
}

/**
 * @param {PointerEvent} event
 */
function onPointerUp(event) {
  if (pointerId.value !== event.pointerId || !pointerStart.value) {
    return;
  }
  if (!props.selectMode && !props.moveInputLocked) {
    const dx = event.clientX - pointerStart.value.x;
    const dy = event.clientY - pointerStart.value.y;
    const direction = directionFromDelta(dx, dy);
    if (direction) {
      emit('move', direction);
    }
  }
  pointerStart.value = null;
  pointerId.value = null;
}

/**
 * @param {number} row
 * @param {number} col
 */
function onCellClick(row, col) {
  if (!props.selectMode) {
    boardRef.value?.focus({ preventScroll: true });
    return;
  }
  emit('cell-select', { row, col });
}

onMounted(() => {
  measureLayer();
  if (typeof ResizeObserver !== 'undefined' && tileLayerRef.value) {
    resizeObserver = new ResizeObserver(() => measureLayer());
    resizeObserver.observe(tileLayerRef.value);
  }
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
});

defineExpose({
  focusBoard() {
    boardRef.value?.focus({ preventScroll: true });
  },
  getCellStridePx() {
    return cellStridePx.value;
  },
  TILE_LAYER_INSET_PX,
  GRID_GAP_PX
});
</script>
