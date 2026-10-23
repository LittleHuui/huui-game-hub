/** 游戏底层组件统一导出 */

export { default as GameShopPanel } from './panels/GameShopPanel.vue';
export { default as GameRankingPanel } from './panels/GameRankingPanel.vue';
export { default as GameInventoryPanel } from './panels/GameInventoryPanel.vue';
export { default as GameResultModal } from './panels/GameResultModal.vue';
export { default as GamePauseOverlay } from './panels/GamePauseOverlay.vue';
export { default as TurnPlayerPanel } from './panels/TurnPlayerPanel.vue';

export { default as GameMatchStatsPanel } from './stats/GameMatchStatsPanel.vue';

export { default as GameControlField } from './controls/GameControlField.vue';
export { default as GameActionBar } from './controls/GameActionBar.vue';
export { default as GameSelectControl } from './controls/GameSelectControl.vue';
export { default as GameRadioGroupControl } from './controls/GameRadioGroupControl.vue';
export { default as GameSwitchControl } from './controls/GameSwitchControl.vue';
export { default as GameNumberInput } from './controls/GameNumberInput.vue';
export { default as TurnActionBar } from './controls/TurnActionBar.vue';
export { default as TurnCountdown } from './controls/TurnCountdown.vue';
export { default as SelectableItemHand } from './controls/SelectableItemHand.vue';

export {
  GAME_ACTION_TYPE,
  GAME_ACTION_SIZE,
  GAME_CONTROL_TYPE,
  GAME_STAT_TONE
} from './controls/gameControlEnums.js';

export {
  STRATEGY_TURN_ACTION_TYPE,
  TURN_ACTION_BAR_KEY
} from './controls/turnControlEnums.js';

export {
  hasActionOfferType,
  getEnumeratedOptionsByActionType,
  resolveStrategyTurnActionLabel
} from './controls/turnActionUtils.js';
