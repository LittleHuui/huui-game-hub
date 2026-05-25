import * as userService from '../../services/userService.js';
import { createNewPuzzle } from './sudokuEngine.js';
import { SUDOKU_CODE, getGivensCountForDifficulty } from './sudokuConfig.js';
import { SUDOKU_PAGE_SETTING_FILTER_UNAVAILABLE } from './sudokuPageSettings.js';

/**
 * 按难度生成新棋盘。
 * @param {string} difficultyCode
 * @returns {{ solution: number[][]; puzzle: number[][]; cells: import('./sudokuEngine.js').SudokuCell[][] }}
 */
export function createBoardForDifficulty(difficultyCode) {
  const givensCount = getGivensCountForDifficulty(difficultyCode);
  return createNewPuzzle(givensCount);
}

/**
 * @param {number} totalSec
 * @returns {string}
 */
export function formatDurationMmSs(totalSec) {
  const sec = Math.max(0, Math.floor(totalSec));
  const minutes = Math.floor(sec / 60);
  const seconds = sec % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

/**
 * @param {Record<number, number>} remaining
 * @returns {string}
 */
export function formatRemainingNumbersMessage(remaining) {
  const parts = [];
  for (let n = 1; n <= 9; n++) {
    parts.push(`${n} 剩余 ${remaining[n] ?? 0}`);
  }
  return parts.join(' · ');
}

/**
 * 是否开启「过滤不可选数字」。
 * @returns {boolean}
 */
export function isFilterUnavailableNumbersEnabled() {
  return userService.readGameSettingBoolean(
    SUDOKU_CODE,
    SUDOKU_PAGE_SETTING_FILTER_UNAVAILABLE.key,
    false
  );
}

/**
 * 保存「过滤不可选数字」偏好（本地缓存 + 在线同步）。
 * @param {boolean} value
 * @returns {Promise<void>}
 */
export async function setFilterUnavailableNumbers(value) {
  await userService.updateGameSetting(SUDOKU_CODE, {
    [SUDOKU_PAGE_SETTING_FILTER_UNAVAILABLE.key]: !!value
  });
}
