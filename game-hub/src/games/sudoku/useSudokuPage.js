import { createSudokuGame } from './SudokuGameService.js';
import { createSudokuPresentation } from './createSudokuPresentation.js';
import { createSudokuInput } from './createSudokuInput.js';
import { computed, onBeforeUnmount, onMounted, reactive } from 'vue';
import SudokuBoard from './components/SudokuBoard.vue';
import SudokuNumberPanel from './components/SudokuNumberPanel.vue';
import { LightSingleGameLayout } from '../../game-templates/light-single/index.js';
import { GameMatchStatsPanel, GameResultModal, GameShopPanel, GameRankingPanel, GameInventoryPanel } from '../../components/game/index.js';
import { SUDOKU_CODE, SUDOKU_MODE, SUDOKU_PROP, getSudokuPropRule } from './sudokuConfig.js';
import { useGameSwitchLock } from '../../composables/useGameSwitchLock.js';
import { usePageVisibilityPause } from '../../composables/usePageVisibilityPause.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import './styles/sudoku.css';

export const pageComponents = {
  SudokuBoard,
  SudokuNumberPanel,
  LightSingleGameLayout,
  GameMatchStatsPanel,
  GameResultModal,
  GameShopPanel,
  GameRankingPanel,
  GameInventoryPanel
};

/** 组合游戏控制、展示与页面生命周期。 @returns {object} */
export function useSudokuPage() {
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
  const input = createSudokuInput();
  let presentation;
  const game = createSudokuGame({
    resultModal,
    ...input,
    openResultModal: (...args) => presentation.openResultModal(...args),
    openResultModalEnd: (...args) => presentation.openResultModalEnd(...args)
  });
  presentation = createSudokuPresentation({ ...game, resultModal });
  const { gameStatus, isPaused, pauseGame, gameMessage, platform, hintMatchLimit, resetRuntime, difficultyCode } = game;

  useGameSwitchLock(
    computed(() => gameStatus.value === 'playing' || gameStatus.value === 'settling')
  );

  usePageVisibilityPause({
    shouldPause: () => gameStatus.value === 'playing' && !isPaused.value,
    pause: () => {
      pauseGame();
      if (isPaused.value) {
        gameMessage.value = '页面隐藏，游戏已暂停';
      }
    }
  });

  onMounted(async () => {
    platform.setCurrentGame(SUDOKU_CODE);
    const rule = getSudokuPropRule(SUDOKU_PROP.HINT);
    if (rule?.maxUsePerMatch != null) {
      hintMatchLimit.value = Number(rule.maxUsePerMatch);
    }
    resetRuntime();
    await activateGame(SUDOKU_CODE, {
      mode: SUDOKU_MODE,
      difficultyCode: difficultyCode.value,
      includeInventory: true
    });
  });

  onBeforeUnmount(() => {
    game.dispose();
  });

  return { ...game, ...input, ...presentation, resultModal };
}
