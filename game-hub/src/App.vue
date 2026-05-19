<template>
  <div id="app-root">
    <BootSyncMask @retry="runBootstrap" />
    <ToastStack />
    <router-view v-if="platform.bootStatus === 'ready' || platform.bootStatus === 'waitingLogin'" />
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import BootSyncMask from './components/BootSyncMask.vue';
import ToastStack from './components/ToastStack.vue';
import { usePlatformStore } from './stores/platformStore.js';
import { initialize } from './services/bootService.js';

const platform = usePlatformStore();

async function runBootstrap() {
  await initialize();
}

onMounted(() => {
  runBootstrap();
});
</script>
