import * as userService from '../../services/userService.js';
import { MINESWEEPER_GAME_CODE } from './minesweeperConfig.js';
import { MINESWEEPER_PAGE_SETTING_HIGHLIGHT_AROUND } from './minesweeperPageSettings.js';

/**
 * @param {number} rows
 * @param {number} cols
 * @returns {import('./minesweeperTypes.js').MinesweeperCell[][]}
 */
export function createEmptyBoard(rows, cols) {
  const board = [];
  for (let row = 0; row < rows; row++) {
    const line = [];
    for (let col = 0; col < cols; col++) {
      line.push({
        row,
        col,
        isMine: false,
        mineCount: 0,
        opened: false,
        flagged: false,
        question: false
      });
    }
    board.push(line);
  }
  return board;
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 */
export function placeMines(board, rows, cols, mines) {
  let count = 0;
  while (count < mines) {
    const row = Math.floor(Math.random() * rows);
    const col = Math.floor(Math.random() * cols);
    const cell = board[row][col];
    if (!cell.isMine) {
      cell.isMine = true;
      count++;
    }
  }
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 */
export function calculateMineCounts(board, rows, cols) {
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const cell = board[row][col];
      if (cell.isMine) {
        continue;
      }
      let mineCount = 0;
      for (let x = -1; x <= 1; x++) {
        for (let y = -1; y <= 1; y++) {
          if (x === 0 && y === 0) {
            continue;
          }
          const newRow = row + x;
          const newCol = col + y;
          if (newRow >= 0 && newRow < rows && newCol >= 0 && newCol < cols) {
            if (board[newRow][newCol].isMine) {
              mineCount++;
            }
          }
        }
      }
      cell.mineCount = mineCount;
    }
  }
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 * @param {number} rows
 * @param {number} cols
 * @param {number} mines
 */
export function initBoard(board, rows, cols, mines) {
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cell = board[r][c];
      cell.isMine = false;
      cell.mineCount = 0;
      cell.opened = false;
      cell.flagged = false;
      cell.question = false;
    }
  }
  placeMines(board, rows, cols, mines);
  calculateMineCounts(board, rows, cols);
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 * @param {number} rows
 * @param {number} cols
 */
export function flattenBoard(board, rows, cols) {
  const out = [];
  if (!board || !Array.isArray(board) || rows <= 0 || cols <= 0) {
    return out;
  }
  for (let r = 0; r < rows; r++) {
    const line = board[r];
    if (!line || !Array.isArray(line)) {
      return out;
    }
    for (let c = 0; c < cols; c++) {
      const cell = line[c];
      if (cell == null) {
        return out;
      }
      out.push(cell);
    }
  }
  return out;
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 * @param {number} rows
 * @param {number} cols
 * @param {number} row
 * @param {number} col
 */
export function getNeighbors(board, rows, cols, row, col) {
  const out = [];
  for (let dr = -1; dr <= 1; dr++) {
    for (let dc = -1; dc <= 1; dc++) {
      if (dr === 0 && dc === 0) {
        continue;
      }
      const r = row + dr;
      const c = col + dc;
      if (r >= 0 && r < rows && c >= 0 && c < cols) {
        out.push(board[r][c]);
      }
    }
  }
  return out;
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 * @param {number} rows
 * @param {number} cols
 */
export function expandZero(board, rows, cols, row, col) {
  for (let x = -1; x <= 1; x++) {
    for (let y = -1; y <= 1; y++) {
      const newRow = row + x;
      const newCol = col + y;
      if (newRow >= 0 && newRow < rows && newCol >= 0 && newCol < cols) {
        const cell = board[newRow][newCol];
        if (!cell.opened && !cell.isMine && !cell.flagged) {
          cell.opened = true;
          if (cell.mineCount === 0) {
            expandZero(board, rows, cols, newRow, newCol);
          }
        }
      }
    }
  }
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell} cell
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 * @param {number} rows
 * @param {number} cols
 */
export function openCell(cell, board, rows, cols) {
  if (cell.opened || cell.flagged) {
    return;
  }
  cell.opened = true;
  if (cell.mineCount === 0) {
    expandZero(board, rows, cols, cell.row, cell.col);
  }
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 * @param {number} rows
 * @param {number} cols
 * @param {number} mines
 */
export function countOpened(board, rows, cols) {
  let n = 0;
  if (!board || !Array.isArray(board)) {
    return 0;
  }
  for (let r = 0; r < rows; r++) {
    const line = board[r];
    if (!line) {
      return n;
    }
    for (let c = 0; c < cols; c++) {
      const cell = line[c];
      if (cell && cell.opened) {
        n++;
      }
    }
  }
  return n;
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 * @param {number} rows
 * @param {number} cols
 */
export function countCorrectFlags(board, rows, cols) {
  let n = 0;
  if (!board || !Array.isArray(board)) {
    return 0;
  }
  for (let r = 0; r < rows; r++) {
    const line = board[r];
    if (!line) {
      return n;
    }
    for (let c = 0; c < cols; c++) {
      const cell = line[c];
      if (cell && cell.flagged && cell.isMine) {
        n++;
      }
    }
  }
  return n;
}

/**
 * @param {import('./minesweeperTypes.js').MinesweeperCell[][]} board
 * @param {number} rows
 * @param {number} cols
 * @param {number} mines
 */
export function isWinState(board, rows, cols, mines) {
  return countOpened(board, rows, cols) === rows * cols - mines;
}

/**
 * 是否开启「周围格高亮」。
 * @returns {boolean}
 */
export function isHighlightAroundCellsEnabled() {
  return userService.readGameSettingBoolean(
    MINESWEEPER_GAME_CODE,
    MINESWEEPER_PAGE_SETTING_HIGHLIGHT_AROUND.key,
    true
  );
}

/**
 * 保存「周围格高亮」偏好（本地缓存 + 在线同步）。
 * @param {boolean} value
 * @returns {Promise<void>}
 */
export async function setHighlightAroundCells(value) {
  await userService.updateGameSetting(MINESWEEPER_GAME_CODE, {
    [MINESWEEPER_PAGE_SETTING_HIGHLIGHT_AROUND.key]: !!value
  });
}
