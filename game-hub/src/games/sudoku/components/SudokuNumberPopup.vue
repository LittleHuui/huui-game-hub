<template>
  <div
    v-if="visible"
    ref="rootRef"
    class="sudoku-number-popup"
    :class="placementClass"
    :style="positionStyle"
    role="dialog"
    aria-label="选择数字"
    @mousedown.stop
  >
    <div class="sudoku-number-popup__grid">
      <button
        v-for="n in 9"
        :key="n"
        type="button"
        class="sudoku-number-popup__btn"
        :class="{ 'sudoku-number-popup__btn--disabled': isDisabled(n) }"
        :disabled="isDisabled(n)"
        @click.stop="onPick(n)"
      >
        {{ n }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  position: {
    type: Object,
    default: null
  },
  /** @type {import('vue').PropType<Record<number, boolean>>} */
  availableNumbers: {
    type: Object,
    default: () => ({})
  },
  placement: {
    type: String,
    default: 'bottom'
  }
});

const emit = defineEmits(['pick', 'close']);

const rootRef = ref(null);
const popupSize = ref({ width: 0, height: 0 });

const placementOffsets = {
  'right-bottom': { x: 0.1, y: 0.1 },
  right: { x: 0.1, y: -0.5 },
  'right-top': { x: 0.1, y: -1.1 },
  bottom: { x: -0.5, y: 0.1 },
  top: { x: -0.5, y: -1.1 },
  'left-bottom': { x: -1.1, y: 0.1 },
  left: { x: -1.1, y: -0.5 },
  'left-top': { x: -1.1, y: -1.1 }
};

const placementClass = computed(() => `sudoku-number-popup--${props.placement}`);

const positionStyle = computed(() => {
  const rect = props.position;
  if (!rect) {
    return { top: '50%', left: '50%' };
  }
  const estimatedSize = Math.min(rect.boardWidth, rect.width * 3);
  const popupW = popupSize.value.width || estimatedSize;
  const popupH = popupSize.value.height || estimatedSize;
  const offset = placementOffsets[props.placement] || placementOffsets.bottom;
  const minLeft = -offset.x * popupW;
  const maxLeft = rect.boardWidth - (1 + offset.x) * popupW;
  const minTop = -offset.y * popupH;
  const maxTop = rect.boardHeight - (1 + offset.y) * popupH;
  const left =
    minLeft <= maxLeft ? Math.max(minLeft, Math.min(rect.left, maxLeft)) : rect.boardWidth / 2;
  const top =
    minTop <= maxTop ? Math.max(minTop, Math.min(rect.top, maxTop)) : rect.boardHeight / 2;
  return {
    top: `${top}px`,
    left: `${left}px`
  };
});

function updatePopupSize() {
  const el = rootRef.value;
  if (!el) {
    return;
  }
  const rect = el.getBoundingClientRect();
  popupSize.value = {
    width: rect.width,
    height: rect.height
  };
}

/**
 * @param {number} n
 * @returns {boolean}
 */
function isDisabled(n) {
  return !props.availableNumbers[n];
}

/**
 * @param {number} n
 */
function onPick(n) {
  if (isDisabled(n)) {
    return;
  }
  emit('pick', n);
}

/**
 * @param {MouseEvent} event
 */
function onDocumentPointerDown(event) {
  if (!props.visible) {
    return;
  }
  const el = rootRef.value;
  if (el && el.contains(event.target)) {
    return;
  }
  emitClose(event);
}

/**
 * @param {Event} event
 */
function emitClose(event) {
  if (event.target?.closest?.('.sudoku-cell--editable')) {
    return;
  }
  emit('close');
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      document.addEventListener('mousedown', onDocumentPointerDown, true);
      void nextTick(updatePopupSize);
    } else {
      document.removeEventListener('mousedown', onDocumentPointerDown, true);
    }
  }
);

watch(
  () => props.position,
  () => {
    if (props.visible) {
      void nextTick(updatePopupSize);
    }
  }
);

onMounted(() => {
  if (props.visible) {
    document.addEventListener('mousedown', onDocumentPointerDown, true);
    void nextTick(updatePopupSize);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentPointerDown, true);
});
</script>
