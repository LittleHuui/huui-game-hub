<template>
  <div
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
import { computeCellPx } from './minesweeperBoardLayout.js';

const props = defineProps({
  board: { type: Array, default: () => [] },
  rows: { type: Number, default: 9 },
  cols: { type: Number, default: 9 },
  windowWidth: { type: Number, default: 1200 },
  availableWidth: { type: Number, default: 0 },
  neighborRingKeys: { type: Object, default: () => ({}) }
});

defineEmits(['cell-click', 'cell-right', 'ring-enter', 'ring-leave', 'clear-ring']);

const flat = computed(() => Svc.flattenBoard(props.board, props.rows, props.cols));

const wrapStyle = computed(() => {
  const cellPx = computeCellPx(props.availableWidth, props.cols, props.windowWidth);
  return {
    '--cell': `${cellPx}px`,
    gridTemplateColumns: `repeat(${props.cols}, ${cellPx}px)`
  };
});
</script>
