/** 方块滑动过渡时长（ms） */
export const MOVE_ANIMATION_MS = 180;

/** 合并轻微放大动画时长（ms） */
export const MERGE_ANIMATION_MS = 200;

/** 新格子出现动画时长（ms） */
export const SPAWN_ANIMATION_MS = 170;

/** 道具清除格子动画时长（ms） */
export const CLEAR_ANIMATION_MS = 260;

/** 滑动后等待合并/生成阶段时长（ms） */
export function postSlideAnimationWaitMs(hasMerges) {
  return hasMerges ? Math.max(SPAWN_ANIMATION_MS, MERGE_ANIMATION_MS) : SPAWN_ANIMATION_MS;
}

/**
 * 供棋盘根节点绑定的 CSS 变量，与 JS 等待时长一致。
 * @returns {Record<string, string>}
 */
export function getGame2048AnimationCssVars() {
  return {
    '--game2048-move-duration': `${MOVE_ANIMATION_MS}ms`,
    '--game2048-merge-duration': `${MERGE_ANIMATION_MS}ms`,
    '--game2048-spawn-duration': `${SPAWN_ANIMATION_MS}ms`,
    '--game2048-clear-duration': `${CLEAR_ANIMATION_MS}ms`
  };
}

/**
 * 等待下一帧，确保浏览器先应用起始样式再触发 transition。
 * @returns {Promise<void>}
 */
export function nextFrame() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(resolve);
    });
  });
}
