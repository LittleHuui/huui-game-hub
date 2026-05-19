<template>
  <div class="gh-root">
    <slot name="top" />
    <div class="app-main">
      <slot />
    </div>
  </div>
</template>

<script setup></script>

<style scoped>
.gh-root {
  min-height: 100vh;
}
</style>
