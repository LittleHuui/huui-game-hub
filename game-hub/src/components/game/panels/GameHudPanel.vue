<template>
  <section class="game-card game-hud-panel">
    <h2 v-if="title" class="game-card__title">{{ title }}</h2>
    <div class="game-card__body">
      <slot />
      <div v-if="$slots.actions" class="game-hud-actions">
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: ''
  }
});
</script>

<style scoped>
.game-hud-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 4px;
}
</style>
