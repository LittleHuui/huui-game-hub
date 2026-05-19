<template>
  <div class="panel battle-panel" :class="{ shake: boardShake, victory: gameWin }">
    <div v-if="paused" class="pause-placeholder">游戏已暂停</div>
    <MinesweeperBoard
      v-else
      :board="board"
      :rows="rows"
      :cols="cols"
      :window-width="windowWidth"
      :neighbor-ring-keys="neighborRingKeys"
      :paused="paused"
      @cell-click="$emit('cell-click', $event)"
      @cell-right="$emit('cell-right', $event)"
      @ring-enter="$emit('ring-enter', $event)"
      @ring-leave="$emit('ring-leave', $event)"
      @clear-ring="$emit('clear-ring')"
    />
  </div>
</template>

<script setup>
import MinesweeperBoard from '../MinesweeperBoard.vue';

defineProps({
  board: { type: Array, required: true },
  rows: { type: Number, required: true },
  cols: { type: Number, required: true },
  windowWidth: { type: Number, required: true },
  neighborRingKeys: { type: Object, required: true },
  paused: { type: Boolean, required: true },
  boardShake: { type: Boolean, required: true },
  gameWin: { type: Boolean, required: true }
});

defineEmits(['cell-click', 'cell-right', 'ring-enter', 'ring-leave', 'clear-ring']);
</script>
