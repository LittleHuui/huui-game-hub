<template>
  <div v-if="visible" class="minesweeper-result-banner" role="status">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false }
});
</script>
