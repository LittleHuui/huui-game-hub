<template>
  <header class="app-page-header">
    <div class="app-page-header__title-row">
      <slot name="leading" />
      <h1 :title="title"><slot name="title">{{ title }}</slot></h1>
      <span v-if="meta" class="app-page-header__meta">{{ meta }}</span>
    </div>
    <div v-if="$slots.actions" class="app-page-header__actions"><slot name="actions" /></div>
  </header>
</template>

<script setup>
defineProps({ title: { type: String, default: '' }, meta: { type: String, default: '' } });
</script>
