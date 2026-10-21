import { ref } from 'vue';

/** 管理棋盘定位、高亮和输入展示状态。
 * @returns {object}
 */
export function createSudokuInput() {
  const boardRef = ref(null);
  const popupVisible = ref(false);
  const popupPosition = ref(null);
  const popupPlacement = ref('bottom');

  /** 关闭选数弹层并清除位置。 */
  function closePopup() {
    popupVisible.value = false;
    popupPosition.value = null;
    popupPlacement.value = 'bottom';
  }

  /**
   * @param {number} row
   * @param {number} col
   * @returns {string}
   */
  function getPopupPlacement(row, col) {
    const rowGroup = Math.floor(row / 3);
    const colGroup = Math.floor(col / 3);
    const placementMap = [
      ['right-bottom', 'right', 'right-top'],
      ['bottom', 'bottom', 'top'],
      ['left-bottom', 'left', 'left-top']
    ];
    return placementMap[colGroup]?.[rowGroup] || 'bottom';
  }

  /**
   * @param {number} row
   * @param {number} col
   * @param {MouseEvent} event
   */
  function openPopupForCell(row, col, event) {
    const exposedBoardRef = boardRef.value?.boardRef;
    const boardEl = exposedBoardRef?.value || exposedBoardRef;
    const cellEl = event?.currentTarget;
    if (!boardEl || !cellEl?.getBoundingClientRect) {
      return;
    }
    const boardRect = boardEl.getBoundingClientRect();
    const cellRect = cellEl.getBoundingClientRect();
    popupPosition.value = {
      left: cellRect.left - boardRect.left + cellRect.width / 2,
      top: cellRect.top - boardRect.top + cellRect.height / 2,
      width: cellRect.width,
      height: cellRect.height,
      boardWidth: boardRect.width,
      boardHeight: boardRect.height,
      row,
      col
    };
    popupPlacement.value = getPopupPlacement(row, col);
    popupVisible.value = true;
  }

  return { boardRef, popupVisible, popupPosition, popupPlacement, closePopup, getPopupPlacement, openPopupForCell };
}
