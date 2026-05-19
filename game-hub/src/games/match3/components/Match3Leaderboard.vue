<template>
  <RankingPanel
    game-code="match3"
    difficulty="normal"
    :mode="mode"
    :difficulty-label="mode === 'timed' ? '限时 · 普�? : '无尽 · 普�?"
  />
</template>

<script setup>
import RankingPanel from '../../../components/RankingPanel.vue';

defineProps({
  mode: { type: String, required: true }
});
</script>
