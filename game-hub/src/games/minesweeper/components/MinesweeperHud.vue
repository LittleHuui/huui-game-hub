<template>
  <div class="minesweeper-config">
    <div
      class="difficulty-select"
      :class="{ open: difficultyOpen && !isGameInProgress, 'is-locked': isGameInProgress }"
    >
      <div class="difficulty-trigger" @click="$emit('toggle-difficulty-menu')">
        <span>{{ difficultyLabel }}</span>
        <span class="difficulty-arrow">▼</span>
      </div>
      <div v-if="difficultyOpen && !isGameInProgress" class="difficulty-menu">
        <div
          v-for="item in difficultyOptions"
          :key="item.value"
          class="difficulty-option"
          :class="{ active: difficulty === item.value }"
          @click="$emit('select-difficulty', item.value)"
        >
          {{ item.label }}
        </div>
      </div>
    </div>

    <button v-if="isGameInProgress" type="button" class="warning side-action" @click="$emit('toggle-pause')">
      {{ paused ? '继续游戏' : '暂停游戏' }}
    </button>
    <button
      type="button"
      class="side-action"
      :class="isGameInProgress ? 'btn-action-restart' : 'btn-action-start'"
      @click="$emit('start-or-restart')"
    >
      {{ isGameInProgress ? '重开游戏' : '开始游戏' }}
    </button>
    <button v-if="canUseSafeStartHint" type="button" class="side-action btn-action-safe" @click="$emit('safe-start')">
      安全开局
    </button>
    <button v-if="isGameInProgress" type="button" class="side-action btn-action-end" @click="$emit('end-game')">
      结束对局
    </button>
  </div>
</template>

<script setup>
defineProps({
  difficultyLabel: { type: String, required: true },
  difficultyOpen: { type: Boolean, required: true },
  isGameInProgress: { type: Boolean, required: true },
  paused: { type: Boolean, required: true },
  canUseSafeStartHint: { type: Boolean, required: true },
  difficulty: { type: String, required: true },
  difficultyOptions: { type: Array, required: true }
});

defineEmits([
  'toggle-difficulty-menu',
  'select-difficulty',
  'toggle-pause',
  'start-or-restart',
  'safe-start',
  'end-game'
]);
</script>
