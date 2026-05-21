/** 2048 棋盘边长（标准 4×4） */
export const GAME2048_SIZE = 4;

/** @typedef {'up'|'down'|'left'|'right'} Game2048Direction */

/** @typedef {{ id: number; value: number; row: number; col: number }} Game2048Tile */

/** @typedef {{ id: number; fromRow: number; fromCol: number; toRow: number; toCol: number }} Game2048Slide */

/** @typedef {{ id: number; row: number; col: number; value: number }} Game2048MergeMark */

let nextTileId = 1;

/**
 * 重置格子 id 计数器（新局前调用）。
 */
export function resetTileIdCounter() {
  nextTileId = 1;
}

/**
 * 创建带 id 的格子。
 * @param {number} value
 * @param {number} row
 * @param {number} col
 * @returns {Game2048Tile}
 */
export function createTile(value, row, col) {
  return { id: nextTileId++, value, row, col };
}

/**
 * 创建空棋盘。
 * @param {number} [size]
 * @returns {number[][]}
 */
export function createEmptyBoard(size = GAME2048_SIZE) {
  return Array.from({ length: size }, () => Array(size).fill(0));
}

/**
 * 深拷贝棋盘。
 * @param {number[][]} board
 * @returns {number[][]}
 */
export function cloneBoard(board) {
  return board.map((row) => row.slice());
}

/**
 * 由 tile 列表生成数值棋盘。
 * @param {Game2048Tile[]} tiles
 * @param {number} [size]
 * @returns {number[][]}
 */
export function tilesToGrid(tiles, size = GAME2048_SIZE) {
  const grid = createEmptyBoard(size);
  for (const tile of tiles) {
    if (tile.row >= 0 && tile.row < size && tile.col >= 0 && tile.col < size) {
      grid[tile.row][tile.col] = tile.value;
    }
  }
  return grid;
}

/**
 * 棋盘是否相等。
 * @param {number[][]} a
 * @param {number[][]} b
 * @returns {boolean}
 */
function boardsEqual(a, b) {
  for (let r = 0; r < a.length; r++) {
    for (let c = 0; c < a[r].length; c++) {
      if (a[r][c] !== b[r][c]) {
        return false;
      }
    }
  }
  return true;
}

/**
 * 随机选取空格。
 * @param {number[][]} board
 * @returns {{ row: number; col: number }|null}
 */
function pickRandomEmptyCell(board) {
  const empties = [];
  for (let r = 0; r < board.length; r++) {
    for (let c = 0; c < board[r].length; c++) {
      if (board[r][c] === 0) {
        empties.push({ row: r, col: c });
      }
    }
  }
  if (empties.length === 0) {
    return null;
  }
  return empties[Math.floor(Math.random() * empties.length)];
}

/**
 * 在空格生成一个数字（90% 为 2，10% 为 4）。
 * @param {number[][]} board
 * @returns {number[][]}
 */
export function spawnRandomTile(board) {
  const cell = pickRandomEmptyCell(board);
  if (!cell) {
    return cloneBoard(board);
  }
  const next = cloneBoard(board);
  next[cell.row][cell.col] = Math.random() < 0.9 ? 2 : 4;
  return next;
}

/**
 * 在 tile 列表中随机生成一格。
 * @param {Game2048Tile[]} tiles
 * @param {number} [size]
 * @returns {{ tiles: Game2048Tile[]; spawn: Game2048Tile|null }}
 */
export function spawnRandomTileOnTiles(tiles, size = GAME2048_SIZE) {
  const grid = tilesToGrid(tiles, size);
  const cell = pickRandomEmptyCell(grid);
  if (!cell) {
    return { tiles: [...tiles], spawn: null };
  }
  const value = Math.random() < 0.9 ? 2 : 4;
  const spawn = createTile(value, cell.row, cell.col);
  return { tiles: [...tiles, spawn], spawn };
}

/**
 * 开局生成 2 个初始数字（数值棋盘）。
 * @param {number} [size]
 * @returns {number[][]}
 */
export function createInitialBoard(size = GAME2048_SIZE) {
  let board = createEmptyBoard(size);
  board = spawnRandomTile(board);
  board = spawnRandomTile(board);
  return board;
}

/**
 * 开局生成 2 个带 id 的初始格子。
 * @param {number} [size]
 * @returns {Game2048Tile[]}
 */
export function createInitialTiles(size = GAME2048_SIZE) {
  resetTileIdCounter();
  let tiles = [];
  ({ tiles } = spawnRandomTileOnTiles(tiles, size));
  ({ tiles } = spawnRandomTileOnTiles(tiles, size));
  return tiles;
}

/**
 * 单行向左压缩并合并（每格最多合并一次）。
 * @param {number[]} line
 * @returns {{ line: number[]; scoreDelta: number; mergedCols: number[] }}
 */
function slideAndMergeLine(line) {
  const nonZero = line.filter((v) => v !== 0);
  const merged = [];
  const mergedCols = [];
  let scoreDelta = 0;
  let i = 0;
  let outCol = 0;
  while (i < nonZero.length) {
    if (i + 1 < nonZero.length && nonZero[i] === nonZero[i + 1]) {
      const value = nonZero[i] * 2;
      merged.push(value);
      mergedCols.push(outCol);
      scoreDelta += value;
      i += 2;
    } else {
      merged.push(nonZero[i]);
      i += 1;
    }
    outCol += 1;
  }
  while (merged.length < line.length) {
    merged.push(0);
  }
  return { line: merged, scoreDelta, mergedCols };
}

/**
 * 提取矩阵的一行或列。
 * @param {number[][]} board
 * @param {Game2048Direction} direction
 * @param {number} index
 * @returns {number[]}
 */
function extractLine(board, direction, index) {
  const size = board.length;
  if (direction === 'left') {
    return board[index].slice();
  }
  if (direction === 'right') {
    return board[index].slice().reverse();
  }
  if (direction === 'up') {
    const line = [];
    for (let r = 0; r < size; r++) {
      line.push(board[r][index]);
    }
    return line;
  }
  const line = [];
  for (let r = size - 1; r >= 0; r--) {
    line.push(board[r][index]);
  }
  return line;
}

/**
 * 将处理后的行/列写回棋盘。
 * @param {number[][]} board
 * @param {Game2048Direction} direction
 * @param {number} index
 * @param {number[]} line
 * @returns {number[][]}
 */
function writeLine(board, direction, index, line) {
  const next = cloneBoard(board);
  const size = board.length;
  if (direction === 'left') {
    next[index] = line.slice();
    return next;
  }
  if (direction === 'right') {
    next[index] = line.slice().reverse();
    return next;
  }
  if (direction === 'up') {
    for (let r = 0; r < size; r++) {
      next[r][index] = line[r];
    }
    return next;
  }
  for (let r = 0; r < size; r++) {
    next[size - 1 - r][index] = line[r];
  }
  return next;
}

/**
 * 向指定方向滑动并合并（数值棋盘）。
 * @param {number[][]} board
 * @param {Game2048Direction} direction
 * @returns {{ board: number[][]; scoreDelta: number; moved: boolean; mergeCells: { row: number; col: number; value: number }[] }}
 */
export function moveBoard(board, direction) {
  const size = board.length;
  let working = cloneBoard(board);
  let totalScore = 0;
  const mergeCells = [];

  for (let i = 0; i < size; i++) {
    const line = extractLine(working, direction, i);
    const { line: mergedLine, scoreDelta, mergedCols } = slideAndMergeLine(line);
    totalScore += scoreDelta;
    working = writeLine(working, direction, i, mergedLine);

    for (const colIndex of mergedCols) {
      let row = i;
      let col = colIndex;
      if (direction === 'right') {
        col = size - 1 - colIndex;
      } else if (direction === 'up') {
        row = colIndex;
        col = i;
      } else if (direction === 'down') {
        row = size - 1 - colIndex;
        col = i;
      }
      const value = working[row][col];
      if (value > 0) {
        mergeCells.push({ row, col, value });
      }
    }
  }

  const moved = !boardsEqual(board, working);
  return {
    board: working,
    scoreDelta: totalScore,
    moved,
    mergeCells
  };
}

/**
 * 按方向取一行/列上的格子（已按移动方向排序）。
 * @param {Game2048Tile[]} tiles
 * @param {Game2048Direction} direction
 * @param {number} index
 * @returns {Game2048Tile[]}
 */
function tilesOnLine(tiles, direction, index) {
  if (direction === 'left' || direction === 'right') {
    const row = index;
    const line = tiles.filter((t) => t.row === row);
    line.sort((a, b) => (direction === 'left' ? a.col - b.col : b.col - a.col));
    return line;
  }
  const col = index;
  const line = tiles.filter((t) => t.col === col);
  line.sort((a, b) => (direction === 'up' ? a.row - b.row : b.row - a.row));
  return line;
}

/**
 * 将行内格子写入绝对坐标（slot 为行内从左/上起第几格）。
 * @param {Game2048Tile} tile
 * @param {Game2048Direction} direction
 * @param {number} lineIndex 行或列索引
 * @param {number} slot 行内槽位（0 为最靠移动方向反侧）
 * @param {number} size
 * @returns {Game2048Tile}
 */
function placeTileOnBoard(tile, direction, lineIndex, slot, size) {
  if (direction === 'left') {
    return { ...tile, row: lineIndex, col: slot };
  }
  if (direction === 'right') {
    return { ...tile, row: lineIndex, col: size - 1 - slot };
  }
  if (direction === 'up') {
    return { ...tile, row: slot, col: lineIndex };
  }
  return { ...tile, row: size - 1 - slot, col: lineIndex };
}

/**
 * 处理单行/列 tile 移动与合并。
 * @param {Game2048Tile[]} lineTiles
 * @param {Game2048Direction} direction
 * @param {number} index
 * @param {number} size
 * @returns {{ lineTiles: Game2048Tile[]; scoreDelta: number; slides: Game2048Slide[]; merges: Game2048MergeMark[]; removedIds: number[]; moved: boolean }}
 */
function processTileLine(lineTiles, direction, index, size) {
  const slides = [];
  const merges = [];
  const removedIds = [];
  let scoreDelta = 0;
  let moved = false;
  const result = [];
  let i = 0;

  while (i < lineTiles.length) {
    const current = lineTiles[i];
    if (i + 1 < lineTiles.length && lineTiles[i + 1].value === current.value) {
      const partner = lineTiles[i + 1];
      const slot = result.length;
      const mergedValue = current.value * 2;
      const target = placeTileOnBoard(
        { id: current.id, value: mergedValue, row: 0, col: 0 },
        direction,
        index,
        slot,
        size
      );

      slides.push({
        id: current.id,
        fromRow: current.row,
        fromCol: current.col,
        toRow: target.row,
        toCol: target.col
      });
      slides.push({
        id: partner.id,
        fromRow: partner.row,
        fromCol: partner.col,
        toRow: target.row,
        toCol: target.col
      });
      merges.push({ id: current.id, row: target.row, col: target.col, value: mergedValue });
      removedIds.push(partner.id);
      scoreDelta += mergedValue;
      result.push({ id: current.id, value: mergedValue, row: target.row, col: target.col });
      if (current.row !== target.row || current.col !== target.col) {
        moved = true;
      }
      if (partner.row !== target.row || partner.col !== target.col) {
        moved = true;
      }
      i += 2;
    } else {
      const slot = result.length;
      const placed = placeTileOnBoard(current, direction, index, slot, size);
      if (current.row !== placed.row || current.col !== placed.col) {
        moved = true;
        slides.push({
          id: current.id,
          fromRow: current.row,
          fromCol: current.col,
          toRow: placed.row,
          toCol: placed.col
        });
      }
      result.push(placed);
      i += 1;
    }
  }

  return { lineTiles: result, scoreDelta, slides, merges, removedIds, moved };
}

/**
 * 带 id 的滑动合并，返回位移与合并信息供 UI 动画。
 * @param {Game2048Tile[]} tiles
 * @param {Game2048Direction} direction
 * @param {number} [size]
 * @returns {{ tiles: Game2048Tile[]; scoreDelta: number; moved: boolean; slides: Game2048Slide[]; merges: Game2048MergeMark[]; mergeCells: { row: number; col: number; value: number }[] }}
 */
export function moveTiles(tiles, direction, size = GAME2048_SIZE) {
  const slides = [];
  const merges = [];
  const removedIds = new Set();
  let scoreDelta = 0;
  let moved = false;
  let nextTiles = [];

  for (let i = 0; i < size; i++) {
    const line = tilesOnLine(tiles, direction, i);
    const lineResult = processTileLine(line, direction, i, size);
    scoreDelta += lineResult.scoreDelta;
    if (lineResult.moved) {
      moved = true;
    }
    slides.push(...lineResult.slides);
    merges.push(...lineResult.merges);
    for (const id of lineResult.removedIds) {
      removedIds.add(id);
    }
    nextTiles.push(...lineResult.lineTiles);
  }

  const mergeCells = merges.map((m) => ({ row: m.row, col: m.col, value: m.value }));

  return {
    tiles: nextTiles,
    scoreDelta,
    moved,
    slides,
    merges,
    mergeCells
  };
}

/**
 * 是否存在可移动方向。
 * @param {number[][]} board
 * @returns {boolean}
 */
export function canMove(board) {
  const directions = ['up', 'down', 'left', 'right'];
  for (const dir of directions) {
    if (moveBoard(board, dir).moved) {
      return true;
    }
  }
  return false;
}

/**
 * tile 列表是否可移动。
 * @param {Game2048Tile[]} tiles
 * @param {number} [size]
 * @returns {boolean}
 */
export function canMoveTiles(tiles, size = GAME2048_SIZE) {
  return canMove(tilesToGrid(tiles, size));
}

/**
 * 是否无路可走（游戏结束）。
 * @param {number[][]} board
 * @returns {boolean}
 */
export function isGameOver(board) {
  return !canMove(board);
}

/**
 * tile 列表是否游戏结束。
 * @param {Game2048Tile[]} tiles
 * @param {number} [size]
 * @returns {boolean}
 */
export function isGameOverTiles(tiles, size = GAME2048_SIZE) {
  return isGameOver(tilesToGrid(tiles, size));
}

/**
 * 棋盘最大数字。
 * @param {number[][]} board
 * @returns {number}
 */
export function getMaxTile(board) {
  let max = 0;
  for (const row of board) {
    for (const v of row) {
      if (v > max) {
        max = v;
      }
    }
  }
  return max;
}

/**
 * tile 列表最大数字。
 * @param {Game2048Tile[]} tiles
 * @returns {number}
 */
export function getMaxTileFromTiles(tiles) {
  let max = 0;
  for (const t of tiles) {
    if (t.value > max) {
      max = t.value;
    }
  }
  return max;
}

/**
 * 是否已合成 2048（不强制结束）。
 * @param {number[][]} board
 * @returns {boolean}
 */
export function hasReached2048(board) {
  for (const row of board) {
    for (const v of row) {
      if (v >= 2048) {
        return true;
      }
    }
  }
  return false;
}

/**
 * tile 列表是否已达 2048。
 * @param {Game2048Tile[]} tiles
 * @returns {boolean}
 */
export function hasReached2048Tiles(tiles) {
  return tiles.some((t) => t.value >= 2048);
}

/**
 * 清除指定格子（仅非空格）。
 * @param {number[][]} board
 * @param {number} row
 * @param {number} col
 * @returns {{ board: number[][]; ok: boolean; clearedValue: number }}
 */
export function clearCell(board, row, col) {
  const value = board[row]?.[col] ?? 0;
  if (value === 0) {
    return { board: cloneBoard(board), ok: false, clearedValue: 0 };
  }
  const next = cloneBoard(board);
  next[row][col] = 0;
  return { board: next, ok: true, clearedValue: value };
}

/**
 * 清除指定 tile。
 * @param {Game2048Tile[]} tiles
 * @param {number} row
 * @param {number} col
 * @returns {{ tiles: Game2048Tile[]; ok: boolean; clearedValue: number; removedId: number|null }}
 */
export function clearTile(tiles, row, col) {
  const target = tiles.find((t) => t.row === row && t.col === col);
  if (!target || target.value === 0) {
    return { tiles: [...tiles], ok: false, clearedValue: 0, removedId: null };
  }
  return {
    tiles: tiles.filter((t) => t.id !== target.id),
    ok: true,
    clearedValue: target.value,
    removedId: target.id
  };
}

/**
 * 计算清除锤实际扣分（不超过当前分数）。
 * 规则：扣分 = 被删除格子数字；若当前分数不足则扣至 0 分。
 * @param {number} clearedValue 被清除格子数字
 * @param {number} currentScore 当前游戏积分
 * @returns {number} actualPenalty
 */
export function calcClearPenalty(clearedValue, currentScore) {
  const tileValue = Math.max(0, Number(clearedValue) || 0);
  const score = Math.max(0, Number(currentScore) || 0);
  return Math.min(score, tileValue);
}

/**
 * 扣分后游戏积分（不低于 0）。
 * @param {number} currentScore
 * @param {number} penalty
 * @returns {number}
 */
export function applyScorePenalty(currentScore, penalty) {
  return Math.max(0, currentScore - penalty);
}

/**
 * 由拖拽增量解析方向。
 * @param {number} dx
 * @param {number} dy
 * @param {number} [minDistance]
 * @returns {Game2048Direction|null}
 */
export function directionFromDelta(dx, dy, minDistance = 24) {
  if (Math.abs(dx) < minDistance && Math.abs(dy) < minDistance) {
    return null;
  }
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx > 0 ? 'right' : 'left';
  }
  return dy > 0 ? 'down' : 'up';
}

/**
 * 键盘按键映射为方向。
 * @param {string} key
 * @returns {Game2048Direction|null}
 */
export function directionFromKey(key) {
  const map = {
    ArrowUp: 'up',
    ArrowDown: 'down',
    ArrowLeft: 'left',
    ArrowRight: 'right',
    w: 'up',
    W: 'up',
    s: 'down',
    S: 'down',
    a: 'left',
    A: 'left',
    d: 'right',
    D: 'right'
  };
  return map[key] || null;
}
