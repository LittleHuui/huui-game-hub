<template>
  <div
    ref="handRef"
    class="selectable-item-hand"
    :class="{
      'selectable-item-hand--disabled': disabled || busy,
      'selectable-item-hand--selecting': multiple && isSelecting
    }"
    style="touch-action: pan-x pan-y pinch-zoom"
    role="list"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerCancel"
    @lostpointercapture="onPointerCancel"
  >
    <div
      v-for="(item, index) in items"
      :key="item.id"
      :data-item-id="item.id"
      class="selectable-item-hand__item"
      :class="{
        'selectable-item-hand__item--selected':
          !interactionBlocked && !isItemDisabled(item) && isSelected(item.id),
        'selectable-item-hand__item--range-preview':
          !interactionBlocked && !isItemDisabled(item) && rangePreviewIds.includes(item.id),
        'selectable-item-hand__item--disabled': isItemDisabled(item),
        'selectable-item-hand__item--shake':
          !interactionBlocked && !isItemDisabled(item) && shakeItemId === item.id
      }"
      :style="stackItems ? { zIndex: resolveStackOrder(item, index) } : undefined"
      role="listitem"
      tabindex="0"
      @keydown.enter.prevent="onItemClick(item, { detail: 0 })"
      @keydown.space.prevent="onItemClick(item, { detail: 0 })"
      :aria-disabled="isItemDisabled(item)"
      @pointerdown="onItemPointerDown(item, index, $event)"
      @click="onItemClick(item, $event)"
    >
      <slot
        name="item"
        :item="item"
        :index="index"
        :selected="
          !interactionBlocked && !isItemDisabled(item) && isSelected(item.id)
        "
        :disabled="isItemDisabled(item)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useSelectableItemGesture } from './useSelectableItemGesture.js';

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
  },
  /** 选择所属的交互上下文，变化时取消未完成的手势。 */
  selectionContext: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['change', 'illegal-click']);

const interactionBlocked = computed(() => props.disabled || props.busy);

const selectableSet = computed(() => new Set(normalizeIds(props.selectableItemIds)));
const disabledSet = computed(() => new Set(normalizeIds(props.disabledItemIds)));
const selectedSet = computed(() => new Set(normalizeIds(props.selectedItemIds)));

const shakeItemId = ref('');
const handRef = ref(null);
let shakeTimer = null;

const { isSelecting, rangePreviewIds, onItemPointerDown, onPointerMove, onPointerUp, onPointerCancel, onItemClick } =
  useSelectableItemGesture(props, {
    handRef,
    isItemSelectable,
    changeSelection: (ids) => emit('change', ids),
    illegalSelection: onIllegalSelection
  });

onBeforeUnmount(clearShake);

watch(
  () => props.items,
  () => {
    clearShake();
  }
);

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
 * 只用已确认的受控选择驱动抬牌及选中外观，拖动范围单独高亮。
 * @param {string} id
 * @returns {boolean}
 */
function isSelected(id) {
  return selectedSet.value.has(String(id || '').trim());
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
 * 展示一次非法选择反馈。
 * @param {{ id: string; disabled?: boolean }} item
 * @returns {void}
 */
function onIllegalSelection(item) {
  const id = String(item?.id || '').trim();
  if (!id || interactionBlocked.value) return;
  triggerShake(id);
  emit('illegal-click', { id, reason: isItemDisabled(item) ? 'disabled' : 'not-selectable' });
}
</script>
