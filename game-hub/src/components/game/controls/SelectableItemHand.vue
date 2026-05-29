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
        'selectable-item-hand__item--disabled': isItemDisabled(item),
        'selectable-item-hand__item--shake':
          !interactionBlocked && !isItemDisabled(item) && shakeItemId === item.id
      }"
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
          !interactionBlocked && !isItemDisabled(item) && isSelected(item.id)
        "
        :disabled="isItemDisabled(item)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { matchStrategyTurnActions } from '../../../services/strategyTurnActionMatcher.js';
import './turnGame.css';

const props = defineProps({
  /** @type {import('vue').PropType<Array<{ id: string; disabled?: boolean; illegal?: boolean }>>} */
  items: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<string[]>} */
  selectedIds: {
    type: Array,
    default: () => []
  },
  /** 策略回合 matcher 用手牌（未传时回退为 items） */
  handCards: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<{ selection?: object }|null>} */
  legalActions: {
    type: Object,
    default: null
  },
  /** 提示按钮游标 */
  hintCursor: {
    type: Number,
    default: 0
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
  }
});

const emit = defineEmits(['select', 'illegal-click', 'match-change', 'selection-change']);

const interactionBlocked = computed(() => props.disabled || props.busy);

const matchResult = computed(() => {
  if (!props.legalActions?.selection) {
    return null;
  }
  const handCards = props.handCards.length > 0 ? props.handCards : props.items;
  return matchStrategyTurnActions({
    handCards,
    selectedCardIds: props.selectedIds,
    legalActions: props.legalActions,
    hintCursor: props.hintCursor
  });
});

watch(
  matchResult,
  (result) => {
    if (!result) {
      return;
    }
    emit('match-change', result);
  },
  { immediate: true }
);

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

watch(
  () => props.items,
  () => {
    clearShake();
    cancelDragSelection();
  }
);

watch(
  interactionBlocked,
  (blocked) => {
    if (blocked) {
      cancelDragSelection();
    }
  }
);

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
  return (props.selectedIds || []).some((item) => String(item || '').trim() === normalized);
}

/**
 * @param {{ id?: string; disabled?: boolean; illegal?: boolean }} item
 * @returns {boolean}
 */
function isItemDisabled(item) {
  if (interactionBlocked.value || Boolean(item?.disabled)) {
    return true;
  }
  const result = matchResult.value;
  if (!result) {
    return false;
  }
  const id = String(item?.id || '').trim();
  if (!id) {
    return true;
  }
  return result.disabledCardIds.includes(id);
}

/**
 * @param {{ id?: string; illegal?: boolean }} item
 * @returns {boolean}
 */
function isItemIllegal(item) {
  if (Boolean(item?.illegal)) {
    return true;
  }
  const result = matchResult.value;
  if (!result) {
    return false;
  }
  const id = String(item?.id || '').trim();
  if (!id || isSelected(id) || isItemDisabled(item)) {
    return false;
  }
  return !result.selectableCardIds.includes(id);
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
  }, 380);
}

/**
 * 拖拽经过时更新临时选中集合。
 * @param {{ id: string }} item
 */
function trackDragItem(item) {
  const id = String(item?.id || '').trim();
  if (!id || isItemDisabled(item)) {
    return;
  }
  if (!dragSelectedIds.value.includes(id)) {
    dragSelectedIds.value = [...dragSelectedIds.value, id];
  }
}

/**
 * 完成拖拽选牌并交给 matcher 解析。
 */
function finishDragSelection() {
  if (!dragSelecting.value || !dragMoved) {
    cancelDragSelection();
    return;
  }
  const rawSelectedCardIds = [...dragSelectedIds.value];
  const baselineSelection = [...dragBaselineSelection];
  cancelDragSelection();
  if (!rawSelectedCardIds.length || !props.legalActions?.selection) {
    return;
  }
  const handCards = props.handCards.length > 0 ? props.handCards : props.items;
  const result = matchStrategyTurnActions({
    handCards,
    selectedCardIds: rawSelectedCardIds,
    legalActions: props.legalActions,
    hintCursor: props.hintCursor
  });
  const suggested = Array.isArray(result.suggestedSelection) ? result.suggestedSelection : [];
  const hasMatch = Boolean(result.determinedAction) || suggested.length > 0;
  if (hasMatch) {
    emit('selection-change', suggested.length > 0 ? suggested : rawSelectedCardIds);
    return;
  }
  emit('selection-change', baselineSelection);
  if (!interactionBlocked.value) {
    const shakeId = rawSelectedCardIds[rawSelectedCardIds.length - 1] || '';
    if (shakeId) {
      triggerShake(shakeId);
      emit('illegal-click', { id: shakeId, reason: 'drag-no-match' });
    }
  }
}

/**
 * @param {{ id: string }} item
 * @param {number} index
 * @param {MouseEvent} event
 */
function onItemMouseDown(item, index, event) {
  if (interactionBlocked.value || event.button !== 0) {
    return;
  }
  const id = String(item?.id || '').trim();
  if (!id) {
    return;
  }
  if (isItemDisabled(item)) {
    return;
  }
  dragBaselineSelection = [...(props.selectedIds || [])];
  dragSelecting.value = true;
  dragSelectedIds.value = isSelected(id) ? [...props.selectedIds] : [id];
  trackDragItem(item);
}

/**
 * @param {{ id: string }} item
 * @param {number} index
 */
function onItemMouseEnter(item, index) {
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
 * @param {{ id: string; disabled?: boolean; illegal?: boolean }} item
 * @param {number} index
 */
function onItemClick(item, index) {
  if (dragSelecting.value) {
    cancelDragSelection();
  }
  if (dragMoved) {
    dragMoved = false;
    return;
  }
  const id = String(item?.id || '').trim();
  if (!id) {
    return;
  }
  if (interactionBlocked.value) {
    return;
  }
  if (isItemDisabled(item) || isItemIllegal(item)) {
    if (!interactionBlocked.value) {
      triggerShake(id);
      emit('illegal-click', {
        id,
        reason: isItemDisabled(item) ? 'disabled' : 'illegal'
      });
    }
    return;
  }
  emit('select', { id, item, index });
}
</script>
