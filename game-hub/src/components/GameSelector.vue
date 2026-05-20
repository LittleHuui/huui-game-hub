<template>
  <div class="game-selector-row" :class="{ 'game-selector-row--topbar': layout === 'topbar' }">
    <button
      v-for="g in games"
      :key="g.code"
      type="button"
      class="game-selector-pill"
      :class="{
        'is-active': g.code === platform.currentGameCode,
        'is-placeholder': !g.implemented
      }"
      :disabled="!g.playable"
      @click="select(g.code)"
    >
      <span class="game-selector-logo" aria-hidden="true">{{ g.logo || '▪️' }}</span>
      <span class="game-selector-name">{{ g.name }}</span>
      <span v-if="!g.implemented" class="muted-small">（暂未实现）</span>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { usePlatformStore } from '../stores/platformStore.js';
import * as toastService from '../services/toastService.js';
import { GAME_SWITCH_LOCK_DEFAULT_REASON } from '../composables/useGameSwitchLock.js';

defineProps({
  /** topbar：顶栏内紧凑排布；page：独立一行（预留） */
  layout: {
    type: String,
    default: 'page',
    validator: (v) => v === 'page' || v === 'topbar'
  }
});

const platform = usePlatformStore();
const router = useRouter();

const games = computed(() => platform.gameCatalog);

/**
 * 切换当前游戏并导航到对应路由（资源加载由游戏页 onMounted 负责）。
 * @param {string} code
 */
async function select(code) {
  const entry = games.value.find((g) => g.code === code);
  if (!entry?.playable) {
    return;
  }
  if (code === platform.currentGameCode) {
    return;
  }
  if (platform.gameSwitchLocked) {
    toastService.push(
      platform.gameSwitchLockReason || GAME_SWITCH_LOCK_DEFAULT_REASON,
      'warning'
    );
    return;
  }
  platform.setCurrentGame(code);
  await router.push({ name: entry.implemented ? code : 'game-unavailable', params: { gameCode: code } });
}
</script>
