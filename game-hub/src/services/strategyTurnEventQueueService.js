const MOCK_EVENT_PLAY_MS = 280;

/** @type {Set<string>} */
const NON_BLOCKING_EVENT_TYPES = new Set(['gameStarted']);

/** @type {boolean} */
let draining = false;
/** @type {number} */
let playbackGeneration = 0;
/** @type {{ generation: number; events: object[]; onEvent: (event: object) => void | Promise<void>; onComplete: () => void } | null} */
let currentPlayingJob = null;
/** @type {Array<{ generation: number; events: object[]; onEvent: (event: object) => void | Promise<void>; onComplete: () => void }>} */
const pendingJobs = [];

/**
 * 模拟单条事件播放耗时。
 * @returns {Promise<void>}
 */
function waitMockAnimation() {
  return new Promise((resolve) => {
    setTimeout(resolve, MOCK_EVENT_PLAY_MS);
  });
}

/**
 * 按 sequence 升序排列事件。
 * @param {object[]} events
 * @returns {object[]}
 */
function sortEventsBySequence(events) {
  return [...events].sort((left, right) => left.sequence - right.sequence);
}

/**
 * 过滤不参与动画播放的事件。
 * @param {object[]} events
 * @returns {object[]}
 */
export function filterPlaybackEvents(events) {
  return (events || []).filter((event) => {
    const eventType = String(event?.eventType || '').trim();
    return Boolean(eventType) && !NON_BLOCKING_EVENT_TYPES.has(eventType);
  });
}

/**
 * 判断播放代次是否仍有效。
 * @param {number} generation
 * @returns {boolean}
 */
export function isPlaybackGenerationValid(generation) {
  return generation === playbackGeneration;
}

/**
 * 读取当前播放代次。
 * @returns {number}
 */
export function getPlaybackGeneration() {
  return playbackGeneration;
}

/**
 * 递增播放代次并清空尚未开始的任务，使进行中的播放完成后不再回写。
 */
export function invalidateEventPlayback() {
  playbackGeneration += 1;
  pendingJobs.length = 0;
}

/**
 * 顺序消费播放队列。
 * @returns {Promise<void>}
 */
async function drainQueue() {
  if (draining) {
    return;
  }
  draining = true;
  try {
    while (pendingJobs.length > 0) {
      const job = pendingJobs.shift();
      if (!job) {
        continue;
      }
      const generation = job.generation;
      currentPlayingJob = job;
      try {
        const ordered = sortEventsBySequence(job.events);
        for (const event of ordered) {
          if (!isPlaybackGenerationValid(generation)) {
            break;
          }
          await job.onEvent(event);
          if (!isPlaybackGenerationValid(generation)) {
            break;
          }
          await waitMockAnimation();
        }
      } finally {
        currentPlayingJob = null;
      }
      job.onComplete();
    }
  } finally {
    draining = false;
  }
}

/**
 * 将事件列表加入播放队列；全部播放完成后调用 onComplete。
 * @param {{
 *   generation: number;
 *   events: object[];
 *   onEvent?: (event: object) => void | Promise<void>;
 *   onComplete: () => void;
 * }} options
 */
export function enqueueEventPlayback(options) {
  const payload = options && typeof options === 'object' ? options : {};
  const generation = Number(payload.generation);
  if (!Number.isFinite(generation)) {
    return;
  }
  const events = filterPlaybackEvents(Array.isArray(payload.events) ? payload.events : []);
  const onComplete = typeof payload.onComplete === 'function' ? payload.onComplete : () => {};
  const onEvent = typeof payload.onEvent === 'function' ? payload.onEvent : () => {};
  pendingJobs.push({ generation, events, onEvent, onComplete });
  void drainQueue();
}

/**
 * 清空尚未开始的播放任务并使当前代次失效。
 */
export function clearPendingEventPlayback() {
  invalidateEventPlayback();
}

/**
 * 是否仍有待播放或正在播放的任务。
 * @returns {boolean}
 */
export function isEventPlaybackBusy() {
  return currentPlayingJob != null || pendingJobs.length > 0;
}
