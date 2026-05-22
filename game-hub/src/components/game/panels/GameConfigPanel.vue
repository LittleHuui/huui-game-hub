<template>
  <section class="game-card game-config-panel">
    <div v-if="title || $slots['title-extra']" class="game-config-panel__head">
      <h2 v-if="title" class="game-card__title">{{ title }}</h2>
      <slot name="title-extra" />
    </div>
    <div class="game-card__body">
      <slot />
    </div>
  </section>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '游戏设置'
  }
});
</script>
