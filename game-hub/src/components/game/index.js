/** 游戏底层组件统一导出 */

export { default as GamePlayLayout } from './layout/GamePlayLayout.vue';

export { default as GameConfigPanel } from './panels/GameConfigPanel.vue';
export { default as GameHudPanel } from './panels/GameHudPanel.vue';
export { default as GameShopPanel } from './panels/GameShopPanel.vue';
export { default as GameRankingPanel } from './panels/GameRankingPanel.vue';
export { default as GameInventoryPanel } from './panels/GameInventoryPanel.vue';
export { default as GameResultModal } from './panels/GameResultModal.vue';
export { default as GamePauseOverlay } from './panels/GamePauseOverlay.vue';

export { default as GameHudStats } from './stats/GameHudStats.vue';
export { default as GameStatGrid } from './stats/GameStatGrid.vue';
export { default as GameStatCard } from './stats/GameStatCard.vue';
export { default as GameStatQuotaBar } from './stats/GameStatQuotaBar.vue';
export { default as GameMatchStatsPanel } from './stats/GameMatchStatsPanel.vue';

export { default as GameControlPanel } from './controls/GameControlPanel.vue';
export { default as GameControlField } from './controls/GameControlField.vue';
export { default as GameActionBar } from './controls/GameActionBar.vue';
export { default as GameSelectControl } from './controls/GameSelectControl.vue';
export { default as GameRadioGroupControl } from './controls/GameRadioGroupControl.vue';
export { default as GameSwitchControl } from './controls/GameSwitchControl.vue';

export {
  GAME_ACTION_TYPE,
  GAME_ACTION_SIZE,
  GAME_CONTROL_TYPE,
  GAME_STAT_TONE
} from './controls/gameControlEnums.js';
