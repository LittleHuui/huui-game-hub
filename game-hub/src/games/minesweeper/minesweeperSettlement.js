import { countCorrectFlags } from './minesweeperEngine.js';
import { MINESWEEPER_MODE, MINESWEEPER_PRESETS } from './minesweeperConfig.js';

// 当前客户端与积分说明共同使用的口径；不把尚未接入的远端字段改为新规则。
const REWARD_PER_CORRECT_FLAG = 3;
const MILLISECONDS_PER_SECOND = 1000;

/**
 * 保持胜利满积分、失败/主动结束按正确标旗计分的现有结算合同。
 * @param {'win'|'fail'|'end'} kind
 * @param {object} round
 * @returns {object}
 */
export function buildMinesweeperSettlement(kind, round) {
  const score = kind === 'win'
    ? MINESWEEPER_PRESETS[round.difficultyCode].scoreWin
    : countCorrectFlags(round.board, round.rows, round.cols) * REWARD_PER_CORRECT_FLAG;
  return {
    score,
    difficultyCode: round.difficultyCode,
    durationMs: Math.round(round.elapsedSec * MILLISECONDS_PER_SECOND),
    mode: MINESWEEPER_MODE,
    propUses: round.propUses,
    sessionId: round.sessionId
  };
}
