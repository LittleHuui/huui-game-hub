<template>
  <div class="room-hub-page room-hub-page--waiting">
    <header class="room-hub-page__toolbar">
      <div class="room-hub-page__toolbar-main">
        <h2 class="room-hub-page__title">正在进入对战...</h2>
      </div>
    </header>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { usePlatformStore } from '../stores/platformStore.js';
import { getGameConfig } from '../constants/gameRegistry.js';

const route = useRoute();
const router = useRouter();
const platform = usePlatformStore();

onMounted(async () => {
  const gameCode = String(route.params.gameCode || '').trim();
  const roomId = String(route.params.roomId || '').trim();
  if (gameCode) {
    platform.setCurrentGame(gameCode);
  }
  if (!gameCode || !roomId) {
    await router.replace({ name: 'game-unavailable', params: { gameCode: gameCode || 'unknown' } });
    return;
  }
  const registry = getGameConfig(gameCode);
  if (!registry || registry.onlineEnabled !== true || !registry.onlinePlayRouteName) {
    await router.replace({ name: 'online-room-list', params: { gameCode } });
    return;
  }
  let routeParams = { roomId };
  if (typeof registry.onlinePlayRouteParamsBuilder === 'function') {
    routeParams = registry.onlinePlayRouteParamsBuilder({ roomId, gameCode }) || routeParams;
  }
  await router.replace({
    name: registry.onlinePlayRouteName,
    params: routeParams
  });
});
</script>
