<template>
  <div
    ref="boardHostRef"
    class="panel battle-panel"
    :class="{ shake: boardShake, victory: gameWin }"
  >
    <MinesweeperBoard
      :board="board"
      :rows="rows"
      :cols="cols"
      :window-width="windowWidth"
      :available-width="boardHostWidth"
      :neighbor-ring-keys="neighborRingKeys"
      @cell-click="$emit('cell-click', $event)"
      @cell-right="$emit('cell-right', $event)"
      @ring-enter="$emit('ring-enter', $event)"
      @ring-leave="$emit('ring-leave', $event)"
      @clear-ring="$emit('clear-ring')"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import MinesweeperBoard from '../MinesweeperBoard.vue';

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
