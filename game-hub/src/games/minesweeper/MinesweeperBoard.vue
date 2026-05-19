<template>
  <div
    v-if="!paused"
    class="board board--adaptive"
    :style="wrapStyle"
    @mouseleave="$emit('clear-ring')"
  >
    <div
      v-for="cell in flat"
      :key="cell.row + '-' + cell.col"
      class="cell"
      :class="{
        opened: cell.opened,
        mine: cell.opened && cell.isMine,
        flag: cell.flagged,
        'cell-neighbor-ring': !!neighborRingKeys[cell.row + '-' + cell.col]
      }"
      @click="$emit('cell-click', cell)"
      @contextmenu.prevent="$emit('cell-right', cell)"
      @mouseenter="$emit('ring-enter', cell)"
      @mouseleave="$emit('ring-leave')"
    >
      <template v-if="cell.opened">
        <span v-if="cell.isMine">💣</span>
        <span v-else-if="cell.mineCount > 0">{{ cell.mineCount }}</span>
      </template>
      <template v-else>
        <span v-if="cell.flagged">🚩</span>
        <span v-else-if="cell.question">❔</span>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import * as Svc from './minesweeperService.js';

const props = defineProps({
  board: { type: Array, default: () => [] },
  rows: { type: Number, default: 9 },
  cols: { type: Number, default: 9 },
  windowWidth: { type: Number, default: 1200 },
  neighborRingKeys: { type: Object, default: () => ({}) },
  paused: { type: Boolean, default: false }
});

defineEmits(['cell-click', 'cell-right', 'ring-enter', 'ring-leave', 'clear-ring']);

const flat = computed(() => Svc.flattenBoard(props.board, props.rows, props.cols));

const wrapStyle = computed(() => {
  const gap = 2;
  const boardHorizontalPad = 20;
  const w = props.windowWidth || 1200;
  const isStacked = w <= 900;
  const outer = isStacked ? w - 80 : w - 420;
  const innerForCells = Math.max(120, outer - boardHorizontalPad);
  const raw = (innerForCells - (props.cols - 1) * gap) / props.cols;
  let cellPx = Math.floor(raw);
  if (!Number.isFinite(cellPx)) {
    cellPx = 14;
  }
  cellPx = Math.min(32, Math.max(12, cellPx));
  return {
    '--cell': `${cellPx}px`,
    gridTemplateColumns: `repeat(${props.cols}, ${cellPx}px)`
  };
});
</script>
