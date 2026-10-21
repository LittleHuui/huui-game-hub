import { useStrategyTurnRoomLifecycle } from '../../../composables/useStrategyTurnRoomLifecycle.js';
import * as doudizhuService from '../doudizhuService.js';

/**
 * 为斗地主配置公共策略回合房间生命周期。
 * @param {object} input
 * @param {string} input.gameCode
 * @returns {object}
 */
export function useDoudizhuRoomLifecycle(input) {
  const lifecycle = useStrategyTurnRoomLifecycle({
    defaultGameCode: input.gameCode,
    defaultRoomLabel: '斗地主对局',
    loadGameView: doudizhuService.loadRoomGameView
  });
  return {
    ...lifecycle,
    onRejoinRoom: lifecycle.rejoin,
    onExitRoomWithShell: lifecycle.exitWithShell,
    onBackToRoom: lifecycle.backToRoomOrLobby,
    reset: lifecycle.reset,
    dispose: lifecycle.dispose
  };
}
