import { createMinesweeperGame } from './MinesweeperGameService.js';
import { createMinesweeperPresentation } from './createMinesweeperPresentation.js';
import { reactive, onMounted, onBeforeUnmount } from 'vue';
import MinesweeperReviveModal from './components/MinesweeperReviveModal.vue';
import MinesweeperBattlePanel from './components/MinesweeperBattlePanel.vue';
import { LightSingleGameLayout } from '../../game-templates/light-single/index.js';
import { GameMatchStatsPanel, GameResultModal, GameShopPanel, GameRankingPanel, GameInventoryPanel } from '../../components/game/index.js';
import { MINESWEEPER_GAME_CODE, MINESWEEPER_MODE } from './minesweeperConfig.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import { useGameSwitchLock } from '../../composables/useGameSwitchLock.js';
import { usePageVisibilityPause } from '../../composables/usePageVisibilityPause.js';

export const pageComponents = {
  MinesweeperReviveModal,
  MinesweeperBattlePanel,
  LightSingleGameLayout,
  GameMatchStatsPanel,
  GameResultModal,
  GameShopPanel,
  GameRankingPanel,
  GameInventoryPanel
};

/** 组合游戏控制、展示与页面生命周期。 @returns {object} */
export function useMinesweeperPage() {
  const resultModal = reactive({
    visible: false,
    title: '本局结算',
    subtitle: '',
    resultType: 'neutral',
    stats: [],
    rewards: [],
    highlights: [],
    actions: []
  });
  let presentation;
  const game = createMinesweeperGame({
    resultModal,
    openResultModal: (...args) => presentation.openResultModal(...args)
  });
  presentation = createMinesweeperPresentation({ ...game, resultModal });
  const { isGameInProgress, isPaused, pauseGame, gameMessage, platform, difficulty, startGame, handleResize } = game;

  useGameSwitchLock(isGameInProgress);

  usePageVisibilityPause({
    shouldPause: () => isGameInProgress.value && !isPaused.value,
    pause: () => {
      pauseGame();
      if (isPaused.value) {
        gameMessage.value = '已离开当前页面，游戏已自动暂停。返回后请点击「继续游戏」。';
      }
    }
  });

  let disposed = false;
  onMounted(async () => {
    platform.setCurrentGame(MINESWEEPER_GAME_CODE);
    await activateGame(MINESWEEPER_GAME_CODE, {
      mode: MINESWEEPER_MODE,
      difficultyCode: difficulty.value,
      includeInventory: true
    });
    if (disposed) return;
    startGame('开始你的扫雷挑战吧');
    window.addEventListener('resize', handleResize);
    handleResize();
  });

  onBeforeUnmount(() => {
    disposed = true;
    window.removeEventListener('resize', handleResize);
    game.dispose();
  });

  return { ...game, ...presentation, resultModal };
}
