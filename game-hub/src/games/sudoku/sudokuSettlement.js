import { countConflictCells, countFilledCells } from './sudokuEngine.js';
import { getSudokuWinReward, SUDOKU_MODE } from './sudokuConfig.js';

const END_REWARD_PER_FILLED_CELL = 2;
const MILLISECONDS_PER_SECOND = 1000;

/**
 * 将当前数独事实转为统一会话结算载荷；保留完成计时及手动结束计分口径。
 * @param {'win'|'end'} kind
 * @param {object} round
 * @returns {{durationMs: number; reward: number; match: object}}
 */
export function buildSudokuSettlement(kind, round) {
  const durationMs = Math.round(round.elapsedSec * MILLISECONDS_PER_SECOND);
  const filledCells = countFilledCells(round.cells);
  const match = {
    difficultyCode: round.difficultyCode,
    durationMs,
    propUses: round.propUses,
    sessionId: round.sessionId,
    mode: SUDOKU_MODE
  };
  if (kind === 'end') {
    const reward = Math.max(0, filledCells * END_REWARD_PER_FILLED_CELL);
    return {
      durationMs,
      reward,
      match: { ...match, score: reward, payload: { filledCells, hintUses: round.hintUses } }
    };
  }
  const reward = getSudokuWinReward(round.elapsedSec, round.difficultyCode);
  const payload = {
    difficultyCode: round.difficultyCode,
    filledCells,
    hintUses: round.hintUses,
    errorCount: countConflictCells(round.cells)
  };
  return {
    durationMs,
    reward,
    match: { ...match, score: durationMs, rewardScore: reward, matchPayload: payload, scorePayload: payload }
  };
}
