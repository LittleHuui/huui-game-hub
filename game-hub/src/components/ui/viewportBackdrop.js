const backdrops = new Set();
let observer;

function syncCanvasBackground() {
  // Root scrollbar gutters paint the canvas background, outside fixed elements.
  const layers = [...backdrops].filter(element => element.getClientRects().length);
  const rootStyle = document.documentElement.style;
  if (!layers.length) {
    rootStyle.removeProperty('--gh-viewport-background');
    return;
  }
  // Only the canvas color (not a background image) paints Chrome's root gutter.
  // Native color compositing keeps nested scrims and CSS color tokens in sync.
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const context = canvas.getContext('2d');
  for (const element of [document.body, ...layers]) {
    context.fillStyle = window.getComputedStyle(element).backgroundColor;
    context.fillRect(0, 0, 1, 1);
  }
  const [red, green, blue] = context.getImageData(0, 0, 1, 1).data;
  rootStyle.setProperty('--gh-viewport-background', `rgb(${red}, ${green}, ${blue})`);
}

export default {
  mounted(element) {
    backdrops.add(element);
    observer ??= new ResizeObserver(syncCanvasBackground);
    observer.observe(element);
    syncCanvasBackground();
  },
  updated: syncCanvasBackground,
  unmounted(element) {
    backdrops.delete(element);
    observer?.unobserve(element);
    if (!backdrops.size) {
      observer?.disconnect();
      observer = undefined;
    }
    syncCanvasBackground();
  }
};
