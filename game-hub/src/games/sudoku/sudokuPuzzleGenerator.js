import { SUDOKU_SIZE as SIZE, SUDOKU_BOX_SIZE as BOX, SUDOKU_SEARCH_NODE_BUDGET } from './sudokuConstants.js';

const MULTIPLE_SOLUTIONS = 2;
const ALL_DIGITS = (1 << SIZE) - 1;

/**
 * 最少候选优先搜索，找到两个解即停止。预算耗尽时保守视作非唯一。
 * 不修改传入棋盘；整个生成过程共享预算，避免难题阻塞页面。
 * @param {number[][]} puzzle
 * @param {{remaining: number}} budget
 * @returns {number}
 */
function countSolutions(puzzle, budget) {
  const grid = puzzle.map((row) => row.slice());
  const rows = Array(SIZE).fill(0);
  const cols = Array(SIZE).fill(0);
  const boxes = Array(SIZE).fill(0);
  const boxIndex = (row, col) => Math.floor(row / BOX) * BOX + Math.floor(col / BOX);
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      const value = grid[row][col];
      if (!value) continue;
      const bit = 1 << (value - 1);
      const box = boxIndex(row, col);
      if ((rows[row] | cols[col] | boxes[box]) & bit) return 0;
      rows[row] |= bit;
      cols[col] |= bit;
      boxes[box] |= bit;
    }
  }

  /** 最少候选优先回溯，耗尽预算只拒绝本次挖空。 @returns {number} */
  function search() {
    if (budget.remaining <= 0) return MULTIPLE_SOLUTIONS;
    budget.remaining--;
    let best = null;
    for (let row = 0; row < SIZE; row++) {
      for (let col = 0; col < SIZE; col++) {
        if (grid[row][col]) continue;
        const box = boxIndex(row, col);
        const mask = ALL_DIGITS & ~(rows[row] | cols[col] | boxes[box]);
        if (!mask) return 0;
        let count = 0;
        for (let bits = mask; bits; bits &= bits - 1) count++;
        if (!best || count < best.count) best = { row, col, box, mask, count };
      }
    }
    if (!best) return 1;
    const { row, col, box } = best;
    let solutions = 0;
    for (let mask = best.mask; mask; mask &= mask - 1) {
      const bit = mask & -mask;
      grid[row][col] = Math.log2(bit) + 1;
      rows[row] |= bit;
      cols[col] |= bit;
      boxes[box] |= bit;
      solutions += search();
      grid[row][col] = 0;
      rows[row] &= ~bit;
      cols[col] &= ~bit;
      boxes[box] &= ~bit;
      if (solutions >= MULTIPLE_SOLUTIONS) return MULTIPLE_SOLUTIONS;
    }
    return solutions;
  }
  return search();
}

/**
 * @param {number[]} values
 * @param {() => number} rng
 * @returns {number[]}
 */
function shuffled(values, rng) {
  const nums = values.slice();
  for (let i = nums.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    const tmp = nums[i];
    nums[i] = nums[j];
    nums[j] = tmp;
  }
  return nums;
}

/**
 * 随机宫带及宫内行列顺序，保持每个九宫格的合法性。
 * @param {() => number} rng
 * @returns {number[]}
 */
function shuffledGroups(rng) {
  const groups = Array.from({ length: BOX }, (_, index) => index);
  return shuffled(groups, rng).flatMap((group) =>
    shuffled(groups, rng).map((offset) => group * BOX + offset)
  );
}

/**
 * 对合法基盘作数字、宫带及宫内行列置换；无回溯，生成成本固定。
 * @param {() => number} [rng]
 * @returns {number[][]}
 */
export function generateSolution(rng = Math.random) {
  const digits = shuffled(Array.from({ length: SIZE }, (_, index) => index + 1), rng);
  const rows = shuffledGroups(rng);
  const cols = shuffledGroups(rng);
  return rows.map((row) => cols.map((col) =>
    digits[(row * BOX + Math.floor(row / BOX) + col) % SIZE]
  ));
}

/**
 * 从终盘逐格挖空；只有仍为唯一解时才保留删除。已知格数是目标下限。
 * @param {number[][]} solution
 * @param {number} givensCount
 * @param {() => number} [rng]
 * @param {{remaining: number}} [budget]
 * @returns {number[][]}
 */
export function carvePuzzleFromSolution(solution, givensCount, rng = Math.random, budget = { remaining: SUDOKU_SEARCH_NODE_BUDGET }) {
  const puzzle = solution.map((row) => row.slice());
  const cells = [];
  for (let row = 0; row < SIZE; row++) {
    for (let col = 0; col < SIZE; col++) {
      cells.push({ row, col });
    }
  }
  for (let i = cells.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    const tmp = cells[i];
    cells[i] = cells[j];
    cells[j] = tmp;
  }
  let remaining = SIZE * SIZE;
  for (const { row, col } of cells) {
    if (remaining <= givensCount || budget.remaining <= 0) {
      break;
    }
    if (puzzle[row][col] === 0) {
      continue;
    }
    const value = puzzle[row][col];
    puzzle[row][col] = 0;
    if (countSolutions(puzzle, budget) === 1) {
      remaining--;
    } else {
      puzzle[row][col] = value;
    }
  }
  return puzzle;
}
