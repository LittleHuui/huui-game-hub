<template>
  <div
    class="selectable-item-hand"
    :class="{ 'selectable-item-hand--disabled': disabled || busy }"
    role="list"
    @mouseleave="onHandMouseLeave"
    @mouseup="onHandMouseUp"
  >
    <div
      v-for="(item, index) in items"
      :key="item.id"
      class="selectable-item-hand__item"
      :class="{
        'selectable-item-hand__item--selected':
          !interactionBlocked && !isItemDisabled(item) && isSelected(item.id),
        'selectable-item-hand__item--drag-selected':
          !interactionBlocked && !isItemDisabled(item) && isDragSelected(item.id),
        'selectable-item-hand__item--disabled': isItemDisabled(item),
        'selectable-item-hand__item--shake':
          !interactionBlocked && !isItemDisabled(item) && shakeItemId === item.id
      }"
      :style="stackItems ? { zIndex: resolveStackOrder(item, index) } : undefined"
      role="listitem"
      :aria-disabled="isItemDisabled(item)"
      @mousedown.prevent="onItemMouseDown(item, index, $event)"
      @mouseenter="onItemMouseEnter(item, index)"
      @click="onItemClick(item, index)"
    >
      <slot
        name="item"
        :item="item"
        :index="index"
        :selected="
          !interactionBlocked && !isItemDisabled(item) && isVisuallySelected(item.id)
        "
        :disabled="isItemDisabled(item)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import './turnGame.css';

const ILLEGAL_SELECTION_FEEDBACK_MS = 380;

const props = defineProps({
  /** @type {import('vue').PropType<Array<{ id: string; disabled?: boolean }>>} */
  items: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<string[]>} */
  selectedItemIds: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<string[]>} */
  selectableItemIds: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<string[]>} */
  disabledItemIds: {
    type: Array,
    default: () => []
  },
  disabled: {
    type: Boolean,
    default: false
  },
  busy: {
    type: Boolean,
    default: false
  },
  /** 是否允许多选 */
  multiple: {
    type: Boolean,
    default: false
  },
  /** 是否按项目顺序建立可预期的层叠关系。 */
  stackItems: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['change', 'illegal-click']);

const interactionBlocked = computed(() => props.disabled || props.busy);

const selectableSet = computed(() => new Set(normalizeIds(props.selectableItemIds)));
const disabledSet = computed(() => new Set(normalizeIds(props.disabledItemIds)));

const shakeItemId = ref('');
/** @type {boolean} */
const dragSelecting = ref(false);
/** @type {string[]} */
const dragSelectedIds = ref([]);
/** @type {string[]} */
let dragBaselineSelection = [];
/** @type {boolean} */
let dragMoved = false;
let shakeTimer = null;

onBeforeUnmount(() => {
  clearShake();
  cancelDragSelection();
});

watch(
  () => props.items,
  () => {
    clearShake();
    cancelDragSelection();
  }
);

watch(interactionBlocked, (blocked) => {
  if (blocked) {
    cancelDragSelection();
  }
});

/**
 * 规范化 ID 列表。
 * @param {string[]|null|undefined} ids
 * @returns {string[]}
 */
function normalizeIds(ids) {
  if (!Array.isArray(ids)) {
    return [];
  }
  const seen = new Set();
  const normalized = [];
  ids.forEach((raw) => {
    const id = String(raw || '').trim();
    if (!id || seen.has(id)) {
      return;
    }
    seen.add(id);
    normalized.push(id);
  });
  return normalized;
}

/**
 * 清理震动状态。
 */
function clearShake() {
  if (shakeTimer != null) {
    clearTimeout(shakeTimer);
    shakeTimer = null;
  }
  shakeItemId.value = '';
}

/**
 * 取消拖拽选牌。
 */
function cancelDragSelection() {
  dragSelecting.value = false;
  dragSelectedIds.value = [];
  dragBaselineSelection = [];
  dragMoved = false;
}

/**
 * @param {string} id
 * @returns {boolean}
 */
function isSelected(id) {
  const normalized = String(id || '').trim();
  if (!normalized) {
    return false;
  }
  return normalizeIds(props.selectedItemIds).includes(normalized);
}

/**
 * 判断牌是否位于当前拖动框选范围。
 * @param {string} id
 * @returns {boolean}
 */
function isDragSelected(id) {
  if (!dragSelecting.value) {
    return false;
  }
  const normalized = String(id || '').trim();
  return Boolean(normalized) && dragSelectedIds.value.includes(normalized);
}

/**
 * 计算操作过程中的可视选中状态。拖动尚未结束时也必须立即给出反馈。
 * @param {string} id
 * @returns {boolean}
 */
function isVisuallySelected(id) {
  return isSelected(id) || isDragSelected(id);
}

/**
 * 计算手牌层级。每张牌始终按从左到右的顺序覆盖，选中和悬停只改变垂直位置。
 * @param {{ id?: string }} item
 * @param {number} index
 * @returns {number}
 */
function resolveStackOrder(item, index) {
  void item;
  return Math.max(0, Number(index) || 0) + 1;
}

/**
 * @param {{ id?: string; disabled?: boolean }} item
 * @returns {boolean}
 */
function isItemDisabled(item) {
  if (interactionBlocked.value || Boolean(item?.disabled)) {
    return true;
  }
  const id = String(item?.id || '').trim();
  if (!id) {
    return true;
  }
  return disabledSet.value.has(id);
}

/**
 * @param {{ id?: string }} item
 * @returns {boolean}
 */
function isItemSelectable(item) {
  const id = String(item?.id || '').trim();
  if (!id || isItemDisabled(item)) {
    return false;
  }
  if (!selectableSet.value.size) {
    return true;
  }
  return selectableSet.value.has(id);
}

/**
 * 触发非法点击震动反馈。
 * @param {string} id
 */
function triggerShake(id) {
  clearShake();
  shakeItemId.value = id;
  shakeTimer = setTimeout(() => {
    shakeItemId.value = '';
    shakeTimer = null;
  }, ILLEGAL_SELECTION_FEEDBACK_MS);
}

/**
 * 拖拽经过时更新临时选中集合。
 * @param {{ id: string }} item
 */
function trackDragItem(item) {
  const id = String(item?.id || '').trim();
  if (!id || !isItemSelectable(item)) {
    return;
  }
  if (!dragSelectedIds.value.includes(id)) {
    dragSelectedIds.value = [...dragSelectedIds.value, id];
  }
}

/**
 * 完成拖拽选牌。
 */
function finishDragSelection() {
  if (!dragSelecting.value || !dragMoved) {
    cancelDragSelection();
    return;
  }
  const nextSelection = normalizeIds(dragSelectedIds.value);
  const baselineSelection = normalizeIds(dragBaselineSelection);
  cancelDragSelection();
  if (!nextSelection.length) {
    return;
  }
  const allSelectable = nextSelection.every((id) => {
    const item = (props.items || []).find((entry) => String(entry?.id || '').trim() === id);
    return item && isItemSelectable(item);
  });
  if (allSelectable) {
    emit('change', nextSelection);
    return;
  }
  emit('change', baselineSelection);
  const shakeId = nextSelection[nextSelection.length - 1] || '';
  if (shakeId && !interactionBlocked.value) {
    triggerShake(shakeId);
    emit('illegal-click', { id: shakeId, reason: 'drag-not-selectable' });
  }
}

/**
 * @param {{ id: string }} item
 * @param {number} index
 * @param {MouseEvent} event
 */
function onItemMouseDown(item, _index, event) {
  if (interactionBlocked.value || event.button !== 0) {
    return;
  }
  const id = String(item?.id || '').trim();
  if (!id || !isItemSelectable(item)) {
    return;
  }
  dragBaselineSelection = normalizeIds(props.selectedItemIds);
  dragSelecting.value = true;
  dragSelectedIds.value = isSelected(id) ? normalizeIds(props.selectedItemIds) : [id];
  trackDragItem(item);
}

/**
 * @param {{ id: string }} item
 * @param {number} index
 */
function onItemMouseEnter(item, _index) {
  if (!dragSelecting.value || interactionBlocked.value) {
    return;
  }
  dragMoved = true;
  trackDragItem(item);
}

function onHandMouseUp() {
  if (!dragSelecting.value) {
    return;
  }
  if (!dragMoved) {
    cancelDragSelection();
    return;
  }
  finishDragSelection();
}

function onHandMouseLeave() {
  if (!dragSelecting.value) {
    return;
  }
  if (!dragMoved) {
    cancelDragSelection();
    return;
  }
  finishDragSelection();
}

/**
 * @param {{ id: string; disabled?: boolean }} item
 * @param {number} index
 */
function onItemClick(item, _index) {
  if (dragSelecting.value) {
    cancelDragSelection();
  }
  if (dragMoved) {
    dragMoved = false;
    return;
  }
  const id = String(item?.id || '').trim();
  if (!id || interactionBlocked.value) {
    return;
  }
  if (!isItemSelectable(item)) {
    triggerShake(id);
    emit('illegal-click', {
      id,
      reason: isItemDisabled(item) ? 'disabled' : 'not-selectable'
    });
    return;
  }
  const current = normalizeIds(props.selectedItemIds);
  if (current.includes(id)) {
    emit('change', current.filter((itemId) => itemId !== id));
    return;
  }
  if (props.multiple) {
    emit('change', [...current, id]);
    return;
  }
  emit('change', [id]);
}
</script>
