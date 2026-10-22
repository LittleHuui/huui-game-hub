<template>
  <div
    class="minesweeper-board"
    :style="wrapStyle"
    @mouseleave="$emit('clear-ring')"
  >
    <button
      v-for="cell in flat"
      :key="cell.row + '-' + cell.col"
      type="button"
      class="minesweeper-cell"
      :aria-label="`第 ${cell.row + 1} 行第 ${cell.col + 1} 列${cell.opened ? (cell.isMine ? '地雷' : cell.mineCount || '空格') : cell.flagged ? '已标记' : '未翻开'}`"
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
        <AppIcon v-if="cell.isMine" name="mine" :size="17" />
        <span v-else-if="cell.mineCount > 0">{{ cell.mineCount }}</span>
      </template>
      <template v-else>
        <AppIcon v-if="cell.flagged" name="flag" :size="17" />
        <span v-else-if="cell.question">?</span>
      </template>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import * as Svc from './minesweeperEngine.js';
import AppIcon from '../../components/ui/AppIcon.vue';

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
  const availableCell = Math.max(28, Math.floor(((props.availableWidth || props.windowWidth) - 28) / props.cols));
  const cellSize = props.cols > 9 ? '32px' : `min(var(--single-mine-cell), ${availableCell}px)`;
  return {
    '--cell': cellSize,
    gridTemplateColumns: `repeat(${props.cols}, var(--cell))`
  };
});
</script>
