/** @typedef {'easy'|'medium'|'hard'} MinesweeperDifficulty */

/** @typedef {object} MinesweeperCell
 * @property {number} row
 * @property {number} col
 * @property {boolean} isMine
 * @property {number} mineCount
 * @property {boolean} opened
 * @property {boolean} flagged
 * @property {boolean} question
 */

export const Difficulty = {
  Easy: 'easy',
  Medium: 'medium',
  Hard: 'hard'
};
