<template>
  <p class="doudizhu-player-tags" aria-label="玩家状态">
    <span v-if="playerState.showCards">明牌</span>
    <span v-if="playerState.isDoubled">加倍</span>
  </p>
</template>

<script setup>
defineProps({
  playerState: { type: Object, default: () => ({}) }
});
</script>
