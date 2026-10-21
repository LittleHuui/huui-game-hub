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

<style scoped>
.doudizhu-player-tags {
  display: flex;
  align-items: center;
  min-height: 16px;
  margin: 0;
  color: #b6c3d5;
  font-size: 11px;
  line-height: 16px;
  white-space: nowrap;
}

.doudizhu-player-tags span + span::before {
  content: '·';
  padding: 0 4px;
  color: #64748b;
}
</style>
