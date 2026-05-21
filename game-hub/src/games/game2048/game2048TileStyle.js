/** 数值 → 格子样式 class（仅 UI，不含游戏规则） */
const TILE_CLASS_BY_VALUE = {
  2: 'tile-2',
  4: 'tile-4',
  8: 'tile-8',
  16: 'tile-16',
  32: 'tile-32',
  64: 'tile-64',
  128: 'tile-128',
  256: 'tile-256',
  512: 'tile-512',
  1024: 'tile-1024',
  2048: 'tile-2048'
};

/**
 * 根据格子数值返回稀有度样式 class。
 * @param {number} value
 * @returns {string}
 */
export function getTileClass(value) {
  if (value <= 0) {
    return '';
  }
  if (TILE_CLASS_BY_VALUE[value]) {
    return TILE_CLASS_BY_VALUE[value];
  }
  if (value >= 4096) {
    return 'tile-super';
  }
  return 'tile-2048';
}
