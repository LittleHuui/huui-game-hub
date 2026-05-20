import { computed, inject, provide, ref, toValue } from 'vue';
import {
  GAME_STAT_THEME_COUNT,
  gameStatThemeVars,
  resolveGameStatThemeIndex
} from '../constants/gameStatThemes.js';

export const GAME_STAT_THEME_KEY = Symbol('gameStatTheme');
export const GAME_STAT_THEME_SLOT_KEY = Symbol('gameStatThemeSlot');

/**
 * 在 HUD 容器注册主题，子组件可基于基准索引偏移配色。
 * @param {import('vue').MaybeRefOrGetter<number|string|undefined>} themeSeed
 */
export function provideGameStatTheme(themeSeed) {
  const themeIndex = computed(() => resolveGameStatThemeIndex(toValue(themeSeed)));
  const themeVars = computed(() => gameStatThemeVars(themeIndex.value));
  const nextSlot = () => {
    const slot = slotCounter.value;
    slotCounter.value += 1;
    return slot;
  };
  const slotCounter = ref(0);
  provide(GAME_STAT_THEME_KEY, { themeIndex, themeVars, nextSlot });
  return { themeIndex, themeVars };
}

/**
 * @param {number|string|undefined} [localSeed]
 * @param {number} [themeOffset] 相对父级主题的配色偏移（无 localSeed 时生效）
 */
export function useGameStatTheme(localSeed, themeOffset = 0) {
  const injected = inject(GAME_STAT_THEME_KEY, null);
  const slotInjected = inject(GAME_STAT_THEME_SLOT_KEY, null);
  const standaloneIndex = ref(resolveGameStatThemeIndex(localSeed));

  const resolvedIndex = computed(() => {
    if (localSeed !== undefined && localSeed !== null && localSeed !== '') {
      return resolveGameStatThemeIndex(localSeed);
    }
    if (injected) {
      const base = injected.themeIndex.value;
      let offset = 0;
      if (themeOffset) {
        offset = themeOffset;
      } else if (typeof slotInjected === 'function') {
        offset = slotInjected();
      }
      return (base + offset) % GAME_STAT_THEME_COUNT;
    }
    return standaloneIndex.value;
  });

  const themeVars = computed(() => gameStatThemeVars(resolvedIndex.value));
  return { themeVars, themeIndex: resolvedIndex };
}

/**
 * 为同一容器内连续子项分配递增主题偏移（统计卡、道具配额等）。
 */
export function useGameStatThemeSlot() {
  const injected = inject(GAME_STAT_THEME_KEY, null);
  const slot = ref(0);
  if (injected?.nextSlot) {
    slot.value = injected.nextSlot();
  }
  provide(GAME_STAT_THEME_SLOT_KEY, () => slot.value);
  return slot;
}
