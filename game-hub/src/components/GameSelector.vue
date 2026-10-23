<template>
  <nav class="game-selector" aria-label="游戏">
    <div class="game-selector-tabs">
      <button v-for="g in games" :key="g.code" type="button" class="game-selector-pill" :class="{ 'is-active': g.code === platform.currentGameCode }" :disabled="!g.playable" :title="!g.playable ? '需要在线连接' : g.name" :aria-current="g.code === platform.currentGameCode ? 'page' : undefined" @click="select(g.code)">{{ g.name }}</button>
    </div>
    <AppMenu class="game-selector-menu" label="切换游戏" title="选择游戏" align="start" :items="menuItems" @select="select">
      <template #trigger><AppIcon :name="gameIcon(platform.currentGameCode)" :size="17" /><span>{{ currentName }}</span><AppIcon name="chevron" :size="12" /></template>
    </AppMenu>
  </nav>
</template>

<script setup>
import { computed } from 'vue';
import AppMenu from './ui/AppMenu.vue';
import AppIcon from './ui/AppIcon.vue';
import { useRouter } from 'vue-router';
import { usePlatformStore } from '../stores/platformStore.js';
import * as toastService from '../services/toastService.js';
import { GAME_SWITCH_LOCK_DEFAULT_REASON } from '../composables/useGameSwitchLock.js';

const platform = usePlatformStore();
const router = useRouter();

const games = computed(() => platform.gameCatalog);
const currentName = computed(() => games.value.find(g => g.code === platform.currentGameCode)?.name || '选择游戏');
const gameIcon = code => ({ minesweeper: 'mine', match3: 'sparkles', game2048: 'grid', '2048': 'grid', sudoku: 'squares-four', uno: 'cards', gomoku: 'circles-four', doudizhu: 'crown' }[code] || 'game-controller');
const menuItems = computed(() => games.value.map(g => ({ id: g.code, label: g.name + (!g.playable ? ' · 需在线' : ''), icon: gameIcon(g.code), disabled: !g.playable, selected: g.code === platform.currentGameCode })));

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
  if (entry.supportOnline && entry.implemented) {
    await router.push({ name: 'online-room-list', params: { gameCode: code } });
    return;
  }
  if (entry.implemented) {
    await router.push({ name: code });
    return;
  }
  await router.push({ name: 'game-unavailable', params: { gameCode: code } });
}
</script>
