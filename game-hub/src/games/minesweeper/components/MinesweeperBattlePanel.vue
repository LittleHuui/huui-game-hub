<template>
  <div class="minesweeper-play">
    <div ref="boardHostRef" class="minesweeper-scroll" :class="{ shake: boardShake, victory: gameWin }" tabindex="0" aria-label="扫雷棋盘，可滚动查看">
      <MinesweeperBoard :board="board" :rows="rows" :cols="cols" :window-width="windowWidth"
        :available-width="boardHostWidth" :neighbor-ring-keys="neighborRingKeys"
        @cell-click="$emit(flagMode ? 'cell-right' : 'cell-click', $event)"
        @cell-right="$emit('cell-right', $event)" @ring-enter="$emit('ring-enter', $event)"
        @ring-leave="$emit('ring-leave', $event)" @clear-ring="$emit('clear-ring')" />
    </div>
    <div class="single-board-tools" role="group" aria-label="点击操作">
      <button type="button" :aria-pressed="!flagMode" :class="{ 'is-active': !flagMode }" @click="flagMode = false"><AppIcon name="mine" :size="16" />翻开</button>
      <button type="button" :aria-pressed="flagMode" :class="{ 'is-active': flagMode }" @click="flagMode = true"><AppIcon name="flag" :size="16" />标记</button>
      <span v-if="cols > 9" class="single-board-tools__hint">滑动查看棋盘</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import MinesweeperBoard from '../MinesweeperBoard.vue';
import AppIcon from '../../../components/ui/AppIcon.vue';
const flagMode = ref(false);

defineProps({
  board: { type: Array, required: true },
  rows: { type: Number, required: true },
  cols: { type: Number, required: true },
  windowWidth: { type: Number, required: true },
  neighborRingKeys: { type: Object, required: true },
  boardShake: { type: Boolean, required: true },
  gameWin: { type: Boolean, required: true }
});

defineEmits(['cell-click', 'cell-right', 'ring-enter', 'ring-leave', 'clear-ring']);

const boardHostRef = ref(null);
const boardHostWidth = ref(0);
let resizeObserver = null;

onMounted(() => {
  const el = boardHostRef.value;
  if (!el) {
    return;
  }
  if (typeof ResizeObserver === 'undefined') {
    boardHostWidth.value = el.clientWidth;
    return;
  }
  resizeObserver = new ResizeObserver((entries) => {
    boardHostWidth.value = entries[0].contentRect.width;
  });
  resizeObserver.observe(el);
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>
