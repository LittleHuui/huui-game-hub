import { createMatch3Game } from './Match3GameService.js';
import { createMatch3Presentation } from './createMatch3Presentation.js';
import { onBeforeUnmount, onMounted, reactive } from 'vue';
import Match3Board from './components/Match3Board.vue';
import { LightSingleGameLayout } from '../../game-templates/light-single/index.js';
import { GameMatchStatsPanel, GameResultModal, GameShopPanel, GameRankingPanel, GameInventoryPanel } from '../../components/game/index.js';
import { useGameSwitchLock } from '../../composables/useGameSwitchLock.js';
import { usePageVisibilityPause } from '../../composables/usePageVisibilityPause.js';
import { activateGame } from '../../services/gameLifecycleService.js';


export const pageComponents = {
  Match3Board,
  LightSingleGameLayout,
  GameMatchStatsPanel,
  GameResultModal,
  GameShopPanel,
  GameRankingPanel,
  GameInventoryPanel
};

/** 组合游戏控制、展示与页面生命周期。 @returns {object} */
export function useMatch3Page() {
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
  const game = createMatch3Game({
    resultModal,
    openResultModal: (...args) => presentation.openResultModal(...args)
  });
  presentation = createMatch3Presentation({ ...game, resultModal });
  const { isGameInProgress, canPauseGame, pauseGame, isPaused, gameMessage, roundCompletion, platform, MATCH3, difficultyCode, mode, isResolutionStale, setupBoard, animationTimeline, stopTimer } = game;

  useGameSwitchLock(isGameInProgress);

  usePageVisibilityPause({
    shouldPause: () => canPauseGame.value,
    pause: () => {
      pauseGame();
      if (isPaused.value) {
        gameMessage.value = '页面隐藏，游戏已暂停';
      }
    }
  });

  onMounted(async () => {
    const gen = roundCompletion.generation;
    platform.setCurrentGame(MATCH3);
    await activateGame(MATCH3, {
      difficultyCode: difficultyCode.value,
      mode: mode.value,
      includeInventory: true
    });
    if (isResolutionStale(gen)) return;
    setupBoard('限时模式，首次有效交换后开始倒计时');
  });

  onBeforeUnmount(() => {
    animationTimeline.cancel();
    roundCompletion.reset();
    stopTimer();
  });

  return { ...game, ...presentation, resultModal };
}
