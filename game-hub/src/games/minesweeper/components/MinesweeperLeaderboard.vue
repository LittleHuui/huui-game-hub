<template>
  <RankingPanel
    game-code="minesweeper"
    :difficulty="difficulty"
    :difficulty-label="difficultyLabel"
  />
</template>

<script setup>
import RankingPanel from '../../../components/RankingPanel.vue';

defineProps({
  difficulty: { type: String, required: true },
  difficultyLabel: { type: String, required: true }
});
</script>
