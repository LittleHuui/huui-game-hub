import { SUDOKU_SIZE as SIZE, SUDOKU_BOX_SIZE as BOX, SUDOKU_MIN_GIVENS, SUDOKU_GENERATION_ATTEMPTS, SUDOKU_SEARCH_NODE_BUDGET } from './sudokuConstants.js';
import { generateSolution, carvePuzzleFromSolution } from './sudokuPuzzleGenerator.js';

/**
 * 是否为可遍历的 9x9 棋盘（首屏 cells 未初始化时需防护）。
 * @param {SudokuCell[][]|null|undefined} cells
 * @returns {boolean}
 */
export function isSudokuGridReady(cells) {
  if (!Array.isArray(cells) || cells.length !== SIZE) {
    return false;
  }
  for (let row = 0; row < SIZE; row++) {
    if (!Array.isArray(cells[row]) || cells[row].length !== SIZE) {
      return false;
    }
  }
  return true;
}

/**
 * @typedef {object} SudokuCell
 * @property {number} row
 * @property {number} col
 * @property {number|null} value
 * @property {number} correctValue
 * @property {boolean} fixed
 * @property {number[]} drafts
 * @property {boolean} conflict
 * @property {boolean} hinted
 */

/**
 * @param {number[][]} puzzle
 * @param {number[][]} solution
 * @returns {SudokuCell[][]}
 */
export function buildCellsFromPuzzle(puzzle, solution) {
  const cells = [];
  for (let row = 0; row < SIZE; row++) {
    const rowCells = [];
    for (let col = 0; col < SIZE; col++) {
      const given = puzzle[row][col];
      const correctValue = solution[row][col];
      const fixed = given > 0;
      rowCells.push({
        row,
        col,
        value: fixed ? given : null,
        correctValue,
        fixed,
        drafts: [],
        conflict: false,
        hinted: false
      });
    }
    cells.push(rowCells);
  }
  return cells;
}

/**
 * @param {number} givensCount
 * @param {() => number} [rng]
 * @returns {{ solution: number[][]; puzzle: number[][]; cells: SudokuCell[][] }}
 */
export function createNewPuzzle(givensCount, rng = Math.random) {
  const target = Math.max(SUDOKU_MIN_GIVENS, Math.min(SIZE * SIZE, Math.floor(Number(givensCount) || SUDOKU_MIN_GIVENS)));
  const budget = { remaining: SUDOKU_SEARCH_NODE_BUDGET };
  let best = null;
  for (let attempt = 0; attempt < SUDOKU_GENERATION_ATTEMPTS; attempt++) {
    const solution = generateSolution(rng);
    const puzzle = carvePuzzleFromSolution(solution, target, rng, budget);
    const givens = puzzle.flat().filter(Boolean).length;
    if (!best || givens < best.givens) best = { solution, puzzle, givens };
    if (givens <= target || budget.remaining <= 0) break;
  }
  const { solution, puzzle } = best;
  const cells = buildCellsFromPuzzle(puzzle, solution);
  refreshCellConflicts(cells);
  return { solution, puzzle, cells };
}

/**
 * 判断指定格填入 value 是否与同行/同列/同宫其他格的正式数字冲突（不含草稿）。
 * @param {SudokuCell[][]} cells
 * @param {number} row
 * @param {number} col
 * @param {number} value
 * @returns {boolean}
 */
export function hasConflict(cells, row, col, value) {
  if (!isSudokuGridReady(cells) || value == null) {
    return false;
  }
  return hasDuplicateConflict(cells, row, col, value);
}

/**
 * 刷新全盘冲突标记（仅依据正式 value 重复，不用 correctValue）。
 * @param {SudokuCell[][]} cells
 */
export function refreshCellConflicts(cells) {
  if (!isSudokuGridReady(cells)) {
    return;
  }
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      const cell = cells[row][col];
      if (cell.fixed || cell.value == null) {
        cell.conflict = false;
        continue;
      }
      cell.conflict = hasConflict(cells, row, col, cell.value);
    }
  }
}

/**
 * @param {SudokuCell[][]} cells
 * @param {number} row
 * @param {number} col
 * @param {number} num
 * @returns {boolean}
 */
function hasDuplicateConflict(cells, row, col, num) {
  for (let c = 0; c < SIZE; c++) {
    if (c !== col && cells[row][c].value === num) {
      return true;
    }
  }
  for (let r = 0; r < SIZE; r++) {
    if (r !== row && cells[r][col].value === num) {
      return true;
    }
  }
  const br = Math.floor(row / BOX) * BOX;
  const bc = Math.floor(col / BOX) * BOX;
  for (let r = br; r < br + BOX; r++) {
    for (let c = bc; c < bc + BOX; c++) {
      if ((r !== row || c !== col) && cells[r][c].value === num) {
        return true;
      }
    }
  }
  return false;
}

/**
 * @param {SudokuCell[][]} cells
 * @returns {Record<number, number>}
 */
export function computeRemainingCounts(cells) {
  const empty = { 1: 9, 2: 9, 3: 9, 4: 9, 5: 9, 6: 9, 7: 9, 8: 9, 9: 9 };
  if (!isSudokuGridReady(cells)) {
    return empty;
  }
  const used = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0 };
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      const v = cells[row][col].value;
      if (v != null && v >= 1 && v <= 9) {
        used[v] += 1;
      }
    }
  }
  const remaining = {};
  for (let n = 1; n <= 9; n++) {
    remaining[n] = 9 - used[n];
  }
  return remaining;
}

/**
 * 获取指定格同行、同列、同宫内已经出现的正式数字。
 * @param {SudokuCell[][]} cells
 * @param {number} row
 * @param {number} col
 * @returns {number[]}
 */
export function getUnavailableNumbers(cells, row, col) {
  if (!isSudokuGridReady(cells) || row < 0 || row >= SIZE || col < 0 || col >= SIZE) {
    return [];
  }
  const unavailable = new Set();
  for (let c = 0; c < SIZE; c++) {
    if (c !== col && cells[row][c].value != null) {
      unavailable.add(cells[row][c].value);
    }
  }
  for (let r = 0; r < SIZE; r++) {
    if (r !== row && cells[r][col].value != null) {
      unavailable.add(cells[r][col].value);
    }
  }
  const br = Math.floor(row / BOX) * BOX;
  const bc = Math.floor(col / BOX) * BOX;
  for (let r = br; r < br + BOX; r++) {
    for (let c = bc; c < bc + BOX; c++) {
      if ((r !== row || c !== col) && cells[r][c].value != null) {
        unavailable.add(cells[r][c].value);
      }
    }
  }
  return Array.from(unavailable);
}

/**
 * 获取指定格可选择的数字表。
 * @param {SudokuCell[][]} cells
 * @param {number} row
 * @param {number} col
 * @param {Record<number, number>} remainingCounts
 * @param {boolean} [filterUnavailable=false] 为 true 时排除同行/同列/同宫已有正式数字
 * @returns {Record<number, boolean>}
 */
export function getAvailableNumbers(cells, row, col, remainingCounts, filterUnavailable = false) {
  const available = {};
  if (!isSudokuGridReady(cells) || row < 0 || row >= SIZE || col < 0 || col >= SIZE) {
    return available;
  }
  const unavailable = filterUnavailable ? new Set(getUnavailableNumbers(cells, row, col)) : new Set();
  const ownValue = cells[row][col].value;
  for (let n = 1; n <= SIZE; n++) {
    const remaining = (remainingCounts?.[n] ?? 0) + (ownValue === n ? 1 : 0);
    available[n] = !unavailable.has(n) && remaining > 0;
  }
  return available;
}

/**
 * @param {SudokuCell[][]} cells
 * @returns {number}
 */
export function countFilledCells(cells) {
  if (!isSudokuGridReady(cells)) {
    return 0;
  }
  let count = 0;
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      if (cells[row][col].value != null) {
        count++;
      }
    }
  }
  return count;
}

/**
 * @param {SudokuCell[][]} cells
 * @returns {number}
 */
export function countEmptyCells(cells) {
  return SIZE * SIZE - countFilledCells(cells);
}

/**
 * @param {SudokuCell[][]} cells
 * @returns {number}
 */
export function countConflictCells(cells) {
  if (!isSudokuGridReady(cells)) {
    return 0;
  }
  let count = 0;
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      if (cells[row][col].conflict) {
        count++;
      }
    }
  }
  return count;
}

/**
 * @param {SudokuCell[][]} cells
 * @returns {boolean}
 */
export function isPuzzleComplete(cells) {
  if (!isSudokuGridReady(cells)) {
    return false;
  }
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      const cell = cells[row][col];
      if (cell.value == null || cell.value !== cell.correctValue) {
        return false;
      }
    }
  }
  return true;
}

/**
 * @param {SudokuCell} cell
 * @returns {boolean}
 */
export function isCellEditable(cell) {
  return cell && !cell.fixed;
}

/**
 * @param {SudokuCell[][]} cells
 * @returns {{ row: number; col: number; cell: SudokuCell }|null}
 */
export function findFirstEmptyEditableCell(cells) {
  if (!isSudokuGridReady(cells)) {
    return null;
  }
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      const cell = cells[row][col];
      if (isCellEditable(cell) && cell.value == null) {
        return { row, col, cell };
      }
    }
  }
  return null;
}

/**
 * @param {SudokuCell} cell
 * @param {number} num
 * @param {{ hinted?: boolean }} [opts]
 */
export function setCellValue(cell, num, opts = {}) {
  cell.value = num;
  cell.drafts = [];
  cell.hinted = !!opts.hinted;
  cell.conflict = false;
}

/**
 * @param {SudokuCell} cell
 * @param {number} num
 */
export function toggleDraft(cell, num) {
  if (!isCellEditable(cell) || cell.value != null) {
    return;
  }
  const idx = cell.drafts.indexOf(num);
  if (idx >= 0) {
    cell.drafts.splice(idx, 1);
  } else {
    cell.drafts.push(num);
    cell.drafts.sort((a, b) => a - b);
  }
}

/**
 * @param {SudokuCell} cell
 */
export function clearCellUserInput(cell) {
  if (!isCellEditable(cell)) {
    return;
  }
  cell.value = null;
  cell.drafts = [];
  cell.hinted = false;
  cell.conflict = false;
}

/**
 * 擦除指定格的用户输入（正式数字或草稿）；固定格与提示格不处理。
 * @param {SudokuCell[][]} cells
 * @param {number} row
 * @param {number} col
 * @returns {boolean} 是否发生了擦除
 */
export function eraseCell(cells, row, col) {
  if (!isSudokuGridReady(cells) || row < 0 || row >= SIZE || col < 0 || col >= SIZE) {
    return false;
  }
  const cell = cells[row][col];
  if (!isCellEditable(cell) || cell.hinted) {
    return false;
  }
  const hasValue = cell.value != null;
  const hasDrafts = Array.isArray(cell.drafts) && cell.drafts.length > 0;
  if (!hasValue && !hasDrafts) {
    return false;
  }
  clearCellUserInput(cell);
  return true;
}
