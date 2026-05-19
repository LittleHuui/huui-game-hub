<template>
  <div
    v-if="platform.bootStatus !== 'ready' && platform.bootStatus !== 'waitingLogin'"
    class="boot-sync-mask"
  >
    <div class="boot-sync-card">
      <template v-if="platform.bootStatus === 'syncing'">
        <div class="boot-spinner" aria-hidden="true" />
        <h1>正在准备</h1>
        <p>{{ platform.syncMessage }}</p>
      </template>
      <template v-else-if="platform.bootStatus === 'error'">
        <h1>无法启动</h1>
        <p>{{ platform.syncMessage }}</p>
        <button type="button" class="success" @click="$emit('retry')">重试</button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { usePlatformStore } from '../stores/platformStore.js';

defineEmits(['retry']);

const platform = usePlatformStore();
</script>
