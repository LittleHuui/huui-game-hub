import { ref, computed, watch } from 'vue';
import { isHighlightAroundCellsEnabled } from './minesweeperSettingsRepository.js';

/** 管理棋盘定位、高亮和输入展示状态。
 * @param {object} context
 * @returns {object}
 */
export function createMinesweeperInput(context) {
  const { rows, cols } = context;
  const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1200);
  const neighborRingKeys = ref({});
  const highlightAroundCells = computed(() => isHighlightAroundCellsEnabled());

  watch(highlightAroundCells, (enabled) => {
    if (!enabled) {
      clearNeighborRing();
    }
  });

  /** 清除鼠标周边格高亮。 @returns {void} */
  function clearNeighborRing() {
    neighborRingKeys.value = {};
  }

  /** 计算棋盘范围内的周边格高亮键。 @param {{row: number; col: number}} center @returns {void} */
  function applyNeighborRingKeysFromCenter(center) {
    const next = {};
    for (let dr = -1; dr <= 1; dr++) {
      for (let dc = -1; dc <= 1; dc++) {
        if (dr === 0 && dc === 0) {
          continue;
        }
        const r = center.row + dr;
        const c = center.col + dc;
        if (r >= 0 && r < rows.value && c >= 0 && c < cols.value) {
          next[`${r}-${c}`] = true;
        }
      }
    }
    neighborRingKeys.value = next;
  }

  /** 仅在已翻开的数字格显示周边高亮。 @param {object} cell @returns {void} */
  function onNeighborRingCellEnter(cell) {
    if (!highlightAroundCells.value) {
      neighborRingKeys.value = {};
      return;
    }
    if (cell.opened && !cell.isMine && cell.mineCount > 0) {
      applyNeighborRingKeysFromCenter(cell);
    } else {
      neighborRingKeys.value = {};
    }
  }

  /** 鼠标离开时取消高亮。 @returns {void} */
  function onNeighborRingCellLeave() {
    clearNeighborRing();
  }

  /** 更新棋盘展示所需的视窗宽度。 @returns {void} */
  function handleResize() {
    windowWidth.value = window.innerWidth;
  }

  return {
    windowWidth,
    neighborRingKeys,
    highlightAroundCells,
    clearNeighborRing,
    applyNeighborRingKeysFromCenter,
    onNeighborRingCellEnter,
    onNeighborRingCellLeave,
    handleResize
  };
}
