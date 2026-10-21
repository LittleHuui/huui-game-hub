/**
 * 将选牌 ID 列表规范化为稳定签名，用于 Preview 响应校验。
 * @param {string[]|null|undefined} cardInstanceIds
 * @returns {string}
 */
export function buildSelectionSignature(cardInstanceIds) {
  if (!Array.isArray(cardInstanceIds)) {
    return '';
  }
  return cardInstanceIds
    .map((id) => String(id || '').trim())
    .filter(Boolean)
    .sort()
    .join(',');
}

/**
 * 创建预览请求控制器，维护递增序号与绑定上下文并丢弃过期响应。
 * @returns {{
 *   nextRequestId: (roomId: string, baseVersion: number, selectionSignature: string) => number;
 *   isCurrent: (requestId: number, roomId: string, baseVersion: number, selectionSignature: string) => boolean;
 *   invalidate: () => void;
 * }}
 */
export function createPreviewRequestController() {
  /** @type {number} */
  let latestRequestId = 0;
  /** @type {boolean} */
  let invalidated = false;
  /** @type {{ requestId: number; roomId: string; baseVersion: number; selectionSignature: string }|null} */
  let boundContext = null;

  return {
    /**
     * 分配新的预览请求序号并绑定上下文。
     * @param {string} roomId
     * @param {number} baseVersion
     * @param {string} selectionSignature
     * @returns {number}
     */
    nextRequestId(roomId, baseVersion, selectionSignature) {
      invalidated = false;
      latestRequestId += 1;
      boundContext = {
        requestId: latestRequestId,
        roomId: String(roomId || '').trim(),
        baseVersion: Number(baseVersion) || 0,
        selectionSignature: String(selectionSignature || '')
      };
      return latestRequestId;
    },
    /**
     * 判断响应是否仍对应当前有效请求。
     * @param {number} requestId
     * @param {string} roomId
     * @param {number} baseVersion
     * @param {string} selectionSignature
     * @returns {boolean}
     */
    isCurrent(requestId, roomId, baseVersion, selectionSignature) {
      if (invalidated || !boundContext) {
        return false;
      }
      if (Number(requestId) !== boundContext.requestId) {
        return false;
      }
      return (
        boundContext.roomId === String(roomId || '').trim() &&
        boundContext.baseVersion === (Number(baseVersion) || 0) &&
        boundContext.selectionSignature === String(selectionSignature || '')
      );
    },
    /**
     * 废弃所有未完成预览响应。
     */
    invalidate() {
      invalidated = true;
      latestRequestId += 1;
      boundContext = null;
    }
  };
}
