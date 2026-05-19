let nextCellId = 1;

/**
 * @param {object} config
 * @returns {string[]}
 */
function itemCodes(config) {
  if (Array.isArray(config?.items) && config.items.length) {
    return config.items.slice(0, config.itemTypes || config.items.length).map((item) => item.itemCode);
  }
  return Array.from({ length: Number(config?.itemTypes) || 6 }, (_, i) => `item_${i}`);
}

/**
 * @param {string} type
 * @param {number} row
 * @param {number} col
 * @returns {object}
 */
function createCell(type, row, col) {
  return {
    id: `m3_${nextCellId++}`,
    type,
    row,
    col
  };
}

/**
 * 深拷贝棋盘（保留 cell 引用结构）。
 * @param {object[][]} board
 * @returns {object[][]}
 */
export function cloneBoard(board) {
  return board.map((row) => row.map((cell) => (cell ? { ...cell } : null)));
}

/**
 * @param {object} from
 * @param {object} to
 * @param {string} id
 * @param {boolean} [isNew]
 * @returns {object}
 */
function dropCellMeta(from, to, id, isNew = false) {
  return {
    id,
    cellId: id,
    from,
    to,
    fromRow: from.row,
    toRow: to.row,
    col: to.col,
    isNew
  };
}

/**
 * @param {number} max
 * @returns {number}
 */
function randomIndex(max) {
  return Math.floor(Math.random() * max);
}

/**
 * @param {object[][]} board
 * @param {number} row
 * @param {number} col
 * @returns {boolean}
 */
function inBounds(board, row, col) {
  return row >= 0 && row < board.length && col >= 0 && col < (board[0]?.length || 0);
}

/**
 * @param {object} a
 * @param {object} b
 * @returns {boolean}
 */
function isAdjacent(a, b) {
  if (!a || !b) {
    return false;
  }
  return Math.abs(a.row - b.row) + Math.abs(a.col - b.col) === 1;
}

/**
 * @param {object[][]} board
 * @param {number} row
 * @param {number} col
 * @param {string} type
 * @returns {boolean}
 */
function createsMatchAt(board, row, col, type) {
  let horizontal = 1;
  for (let c = col - 1; c >= 0 && board[row]?.[c]?.type === type; c--) {
    horizontal++;
  }
  for (let c = col + 1; c < (board[0]?.length || 0) && board[row]?.[c]?.type === type; c++) {
    horizontal++;
  }

  let vertical = 1;
  for (let r = row - 1; r >= 0 && board[r]?.[col]?.type === type; r--) {
    vertical++;
  }
  for (let r = row + 1; r < board.length && board[r]?.[col]?.type === type; r++) {
    vertical++;
  }
  return horizontal >= 3 || vertical >= 3;
}

/**
 * @param {object[][]} board
 * @param {number} row
 * @param {number} col
 * @param {string} type
 * @returns {number}
 */
function dangerLevel(board, row, col, type) {
  if (createsMatchAt(board, row, col, type)) {
    return 1;
  }
  const nearPatterns = [
    [[0, -1], [0, 1]],
    [[-1, 0], [1, 0]],
    [[0, -1], [0, -2]],
    [[0, 1], [0, 2]],
    [[-1, 0], [-2, 0]],
    [[1, 0], [2, 0]]
  ];
  for (const pattern of nearPatterns) {
    const matched = pattern.every(([dr, dc]) => board[row + dr]?.[col + dc]?.type === type);
    if (matched) {
      return 0.6;
    }
  }
  return 0;
}

/**
 * @param {object} config
 * @param {number} score
 * @returns {number}
 */
function friendlinessForScore(config, score) {
  const stages = config?.controlledRandom?.scoreStages || [];
  let result = 0.2;
  for (const stage of stages) {
    if ((Number(score) || 0) >= Number(stage.minScore || 0)) {
      result = Number(stage.friendliness);
    }
  }
  return Number.isFinite(result) ? Math.max(0, Math.min(1, result)) : 0.2;
}

/**
 * @param {object[][]} board
 * @param {object} config
 * @param {number} row
 * @param {number} col
 * @param {number} score
 * @returns {string}
 */
function chooseControlledType(board, config, row, col, score) {
  const codes = itemCodes(config);
  const friendliness = friendlinessForScore(config, score);
  const safe = codes.filter((code) => dangerLevel(board, row, col, code) === 0);
  const maxTries = Math.max(8, codes.length * 3);

  for (let i = 0; i < maxTries; i++) {
    const candidate = codes[randomIndex(codes.length)];
    const danger = dangerLevel(board, row, col, candidate);
    const acceptRate = 1 - danger * (1 - friendliness);
    if (Math.random() <= acceptRate) {
      return candidate;
    }
  }

  if (safe.length) {
    return safe[randomIndex(safe.length)];
  }
  return codes[randomIndex(codes.length)];
}

/**
 * @param {object[][]} board
 * @param {object} a
 * @param {object} b
 */
function swapInPlace(board, a, b) {
  const ca = board[a.row][a.col];
  const cb = board[b.row][b.col];
  board[a.row][a.col] = cb ? { ...cb, row: a.row, col: a.col } : null;
  board[b.row][b.col] = ca ? { ...ca, row: b.row, col: b.col } : null;
}

/**
 * 创建初始棋盘。
 * @param {object} config
 * @returns {object[][]}
 */
export function createBoard(config) {
  const rows = Number(config?.rows) || 9;
  const cols = Number(config?.cols) || 9;
  const codes = itemCodes(config);
  const maxRetries = 240;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const board = Array.from({ length: rows }, () => Array.from({ length: cols }, () => null));
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const safeCodes = codes.filter((code) => !createsMatchAt(board, row, col, code));
        const source = config?.allowInitialMatches === false && safeCodes.length ? safeCodes : codes;
        board[row][col] = createCell(source[randomIndex(source.length)], row, col);
      }
    }
    const validMatches = config?.allowInitialMatches !== false || findMatches(board).length === 0;
    const validMove = config?.requireAtLeastOneMove === false || hasAvailableMove(board);
    if (validMatches && validMove) {
      return board;
    }
  }

  const fallback = Array.from({ length: rows }, (_, row) =>
    Array.from({ length: cols }, (_, col) => createCell(codes[(row + col) % codes.length], row, col))
  );
  return shuffleBoard(fallback, config).board;
}

/**
 * 查找所有横向与纵向三连。
 * @param {object[][]} board
 * @returns {{ direction: string; length: number; cells: { row: number; col: number; id: string; type: string }[] }[]}
 */
export function findMatches(board) {
  const groups = [];
  const rows = board.length;
  const cols = board[0]?.length || 0;

  for (let row = 0; row < rows; row++) {
    let start = 0;
    while (start < cols) {
      const type = board[row][start]?.type;
      let end = start + 1;
      while (type && end < cols && board[row][end]?.type === type) {
        end++;
      }
      if (type && end - start >= 3) {
        groups.push({
          direction: 'row',
          length: end - start,
          cells: Array.from({ length: end - start }, (_, i) => {
            const cell = board[row][start + i];
            return { row, col: start + i, id: cell.id, type: cell.type };
          })
        });
      }
      start = end;
    }
  }

  for (let col = 0; col < cols; col++) {
    let start = 0;
    while (start < rows) {
      const type = board[start][col]?.type;
      let end = start + 1;
      while (type && end < rows && board[end][col]?.type === type) {
        end++;
      }
      if (type && end - start >= 3) {
        groups.push({
          direction: 'col',
          length: end - start,
          cells: Array.from({ length: end - start }, (_, i) => {
            const cell = board[start + i][col];
            return { row: start + i, col, id: cell.id, type: cell.type };
          })
        });
      }
      start = end;
    }
  }
  return groups;
}

/**
 * 判断两个格子交换后是否可消除。
 * @param {object[][]} board
 * @param {{ row: number; col: number }} a
 * @param {{ row: number; col: number }} b
 * @returns {boolean}
 */
export function canSwap(board, a, b) {
  if (!inBounds(board, a?.row, a?.col) || !inBounds(board, b?.row, b?.col) || !isAdjacent(a, b)) {
    return false;
  }
  const next = cloneBoard(board);
  swapInPlace(next, a, b);
  return findMatches(next).length > 0;
}

/**
 * 交换两个相邻格子。
 * @param {object[][]} board
 * @param {{ row: number; col: number }} a
 * @param {{ row: number; col: number }} b
 * @returns {{ board: object[][]; animationSteps: object[] }}
 */
export function swapCells(board, a, b) {
  const next = cloneBoard(board);
  if (!inBounds(next, a?.row, a?.col) || !inBounds(next, b?.row, b?.col) || !isAdjacent(a, b)) {
    return { board: next, animationSteps: [] };
  }
  const left = next[a.row][a.col];
  const right = next[b.row][b.col];
  swapInPlace(next, a, b);
  return {
    board: next,
    animationSteps: [
      {
        type: 'swap',
        cells: [
          { id: left?.id, from: a, to: b },
          { id: right?.id, from: b, to: a }
        ].filter((v) => v.id)
      }
    ]
  };
}

/**
 * 移除匹配格。
 * @param {object[][]} board
 * @param {ReturnType<typeof findMatches>} matches
 * @returns {{ board: object[][]; removedCells: object[]; animationSteps: object[] }}
 */
export function removeMatches(board, matches) {
  const next = cloneBoard(board);
  const byKey = new Map();
  for (const group of matches || []) {
    for (const cell of group.cells || []) {
      byKey.set(`${cell.row}-${cell.col}`, cell);
    }
  }
  const removedCells = Array.from(byKey.values());
  for (const cell of removedCells) {
    if (inBounds(next, cell.row, cell.col)) {
      next[cell.row][cell.col] = null;
    }
  }
  return {
    board: next,
    removedCells,
    animationSteps: [{ type: 'remove', cells: removedCells }]
  };
}

/**
 * 执行下落。
 * @param {object[][]} board
 * @returns {{ board: object[][]; drops: object[]; animationSteps: object[] }}
 */
export function collapseBoard(board) {
  const rows = board.length;
  const cols = board[0]?.length || 0;
  const next = Array.from({ length: rows }, () => Array.from({ length: cols }, () => null));
  const drops = [];

  for (let col = 0; col < cols; col++) {
    let target = rows - 1;
    for (let row = rows - 1; row >= 0; row--) {
      const cell = board[row][col];
      if (!cell) {
        continue;
      }
      next[target][col] = { ...cell, row: target, col };
      if (target !== row) {
        drops.push(dropCellMeta({ row, col }, { row: target, col }, cell.id, false));
      }
      target--;
    }
  }

  return {
    board: next,
    drops,
    animationSteps: drops.length ? [{ type: 'drop', cells: drops }] : []
  };
}

/**
 * 补充空格。
 * @param {object[][]} board
 * @param {object} config
 * @param {number} score
 * @returns {{ board: object[][]; spawns: object[]; animationSteps: object[] }}
 */
export function fillBoardControlled(board, config, score) {
  const next = cloneBoard(board);
  const rows = next.length;
  const cols = next[0]?.length || 0;
  const spawns = [];

  for (let col = 0; col < cols; col++) {
    const emptyRows = [];
    for (let row = 0; row < rows; row++) {
      if (!next[row][col]) {
        emptyRows.push(row);
      }
    }
    emptyRows.forEach((row, index) => {
      const type =
        config?.controlledRandom?.enabled === false
          ? itemCodes(config)[randomIndex(itemCodes(config).length)]
          : chooseControlledType(next, config, row, col, score);
      const cell = createCell(type, row, col);
      next[row][col] = cell;
      spawns.push(
        dropCellMeta({ row: -emptyRows.length + index, col }, { row, col }, cell.id, true)
      );
    });
  }

  return {
    board: next,
    spawns,
    animationSteps: spawns.length ? [{ type: 'spawn', cells: spawns }] : []
  };
}

/**
 * 计算本轮得分。
 * @param {ReturnType<typeof findMatches>} matches
 * @param {object} config
 * @param {number} combo
 * @returns {number}
 */
export function scoreMatches(matches, config, combo) {
  const scored = new Set();
  let score = 0;
  const baseRules = config?.scoreRules?.base || {};
  const comboRules = config?.scoreRules?.comboMultiplier || {};
  for (const group of matches) {
    const key = String(Math.min(group.length, 5));
    const base = Number(baseRules[key] ?? baseRules['3'] ?? 30);
    const perCell = base / Math.max(1, group.length);
    for (const cell of group.cells) {
      const cellKey = `${cell.row}-${cell.col}`;
      if (!scored.has(cellKey)) {
        scored.add(cellKey);
        score += perCell;
      }
    }
  }
  const multiplier = Number(comboRules[String(Math.min(combo, 4))] ?? 1);
  return Math.round(score * multiplier);
}

/**
 * 自动消除直到棋盘稳定。
 * @param {object[][]} board
 * @param {object} config
 * @param {number} score
 * @returns {{ board: object[][]; animationSteps: object[]; scoreDelta: number; comboCount: number; deadBoard: boolean }}
 */
export function resolveBoard(board, config, score) {
  let current = cloneBoard(board);
  const animationSteps = [];
  let scoreDelta = 0;
  let comboCount = 0;

  for (let guard = 0; guard < 40; guard++) {
    const matches = findMatches(current);
    if (!matches.length) {
      break;
    }
    comboCount++;
    animationSteps.push({ type: 'combo', combo: comboCount });
    scoreDelta += scoreMatches(matches, config, comboCount);

    const removed = removeMatches(current, matches);
    current = removed.board;
    animationSteps.push(...removed.animationSteps);

    const collapsed = collapseBoard(current);
    current = collapsed.board;
    animationSteps.push(...collapsed.animationSteps);

    const filled = fillBoardControlled(current, config, (Number(score) || 0) + scoreDelta);
    current = filled.board;
    animationSteps.push(...filled.animationSteps);
  }

  return {
    board: current,
    animationSteps,
    scoreDelta,
    comboCount,
    deadBoard: !hasAvailableMove(current)
  };
}

/**
 * 检查是否存在任意可移动消除。
 * @param {object[][]} board
 * @returns {boolean}
 */
export function hasAvailableMove(board) {
  const rows = board.length;
  const cols = board[0]?.length || 0;
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const right = { row, col: col + 1 };
      const down = { row: row + 1, col };
      if (col + 1 < cols && canSwap(board, { row, col }, right)) {
        return true;
      }
      if (row + 1 < rows && canSwap(board, { row, col }, down)) {
        return true;
      }
    }
  }
  return false;
}

/**
 * 洗牌，保留每种元素数量。
 * @param {object[][]} board
 * @param {object} config
 * @returns {{ board: object[][]; animationSteps: object[] }}
 */
export function shuffleBoard(board, config) {
  const rows = board.length;
  const cols = board[0]?.length || 0;
  const cells = board.flat().filter(Boolean);
  const types = cells.map((cell) => cell.type);

  for (let attempt = 0; attempt < 300; attempt++) {
    const shuffled = [...types].sort(() => Math.random() - 0.5);
    const next = Array.from({ length: rows }, (_, row) =>
      Array.from({ length: cols }, (_, col) => {
        const source = cells[row * cols + col];
        return { ...source, type: shuffled[row * cols + col], row, col };
      })
    );
    const noMatches = config?.allowMatchesAfterShuffle === true || findMatches(next).length === 0;
    const hasMove = config?.requireAtLeastOneMove === false || hasAvailableMove(next);
    if (noMatches && hasMove) {
      return {
        board: next,
        animationSteps: [{ type: 'shuffle', cells: next.flat().map((cell) => ({ id: cell.id })) }]
      };
    }
  }
  return {
    board: cloneBoard(board),
    animationSteps: [{ type: 'shuffle', cells: cells.map((cell) => ({ id: cell.id })) }]
  };
}

/**
 * 使用炸弹清除指定范围。
 * @param {object[][]} board
 * @param {number} row
 * @param {number} col
 * @param {number} [radius]
 * @returns {{ board: object[][]; removedCells: object[]; animationSteps: object[] }}
 */
export function applyBomb(board, row, col, radius = 1) {
  const next = cloneBoard(board);
  const removedCells = [];
  for (let r = row - radius; r <= row + radius; r++) {
    for (let c = col - radius; c <= col + radius; c++) {
      if (!inBounds(next, r, c) || !next[r][c]) {
        continue;
      }
      removedCells.push({ row: r, col: c, id: next[r][c].id, type: next[r][c].type });
      next[r][c] = null;
    }
  }
  return {
    board: next,
    removedCells,
    animationSteps: [{ type: 'bomb', cells: removedCells }]
  };
}
