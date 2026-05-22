const BOARD_GAP = 2;
const BOARD_HORIZONTAL_PAD = 20;

/**
 * 按容器可用宽度计算自适应格子边长（px）。
 * @param {number} availableWidth 棋盘外层容器 content 宽度；0 时使用 defaultWindowWidth
 * @param {number} cols
 * @param {number} [defaultWindowWidth]
 * @returns {number}
 */
export function computeCellPx(availableWidth, cols, defaultWindowWidth = 0) {
  const width =
    availableWidth > 0 ? availableWidth : defaultWindowWidth > 0 ? defaultWindowWidth : 1200;
  const innerWidth = Math.max(120, width - BOARD_HORIZONTAL_PAD);
  const raw = (innerWidth - (cols - 1) * BOARD_GAP) / cols;
  let cellPx = Math.floor(raw);
  if (!Number.isFinite(cellPx)) {
    cellPx = 14;
  }
  return Math.min(32, Math.max(12, cellPx));
}
