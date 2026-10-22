import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const TAP_SLOP_PX = 6;

/**
 * 管理受控手牌的一次指针手势；提交前只预览，不改写外部选择。
 * @param {object} props 受控手牌属性。
 * @param {object} input 手势所需的 DOM 和选择接口。
 * @param {import('vue').Ref<HTMLElement|null>} input.handRef
 * @param {(item: object) => boolean} input.isItemSelectable
 * @param {(ids: string[]) => void} input.changeSelection
 * @param {(item: object) => void} input.illegalSelection
 * @returns {object} 指针处理函数与当前预览。
 */
export function useSelectableItemGesture(props, input) {
  const gesture = ref(null);

  /**
   * 读取不重复的受控选择。
   * @returns {string[]}
   */
  function readSelection() {
    return [...new Set((props.selectedItemIds || []).map((id) => String(id || '').trim()).filter(Boolean))];
  }

  const isSelecting = computed(() => Boolean(gesture.value));
  const rangePreviewIds = computed(() => {
    const current = gesture.value;
    if (!current || !props.multiple) return [];
    const { anchorIndex, endIndex } = current;
    return props.items
      .slice(Math.min(anchorIndex, endIndex), Math.max(anchorIndex, endIndex) + 1)
      .filter(input.isItemSelectable)
      .map((item) => item.id);
  });

  /**
   * 丢弃未完成手势并释放捕获，保留外部已确认的选择。
   * @returns {void}
   */
  function cancelGesture() {
    const pointerId = gesture.value?.pointerId;
    gesture.value = null;
    const hand = input.handRef.value;
    if (pointerId != null && hand?.hasPointerCapture(pointerId)) {
      hand.releasePointerCapture(pointerId);
    }
  }

  /**
   * 捕获后按当前位置命中手牌，兼容鼠标、触摸和笔。
   * @param {PointerEvent} event
   * @returns {number}
   */
  function hitItemIndex(event) {
    const element = document.elementFromPoint(event.clientX, event.clientY)
      ?.closest('.selectable-item-hand__item');
    if (!element || !input.handRef.value?.contains(element)) return -1;
    return props.items.findIndex((item) => String(item.id) === element.dataset.itemId);
  }

  /**
   * 接纳主指针并冻结本次选择基线。
   * @param {object} item
   * @param {number} index
   * @param {PointerEvent} event
   * @returns {void}
   */
  function onItemPointerDown(item, index, event) {
    if (gesture.value || props.disabled || props.busy || event.button !== 0 || event.isPrimary === false) return;
    if (!input.isItemSelectable(item)) {
      input.illegalSelection(item);
      return;
    }
    const baseline = readSelection();
    gesture.value = {
      pointerId: event.pointerId,
      pointerType: event.pointerType,
      startX: event.clientX,
      startY: event.clientY,
      anchorIndex: index,
      endIndex: index,
      baseline,
      removing: baseline.includes(item.id),
      moved: false
    };
    if (event.pointerType !== 'touch') {
      input.handRef.value?.setPointerCapture(event.pointerId);
      event.preventDefault();
    }
  }

  /**
   * 更新连续范围；反向拖回时由同一基线重新计算预览。
   * @param {PointerEvent} event
   * @returns {void}
   */
  function onPointerMove(event) {
    const current = gesture.value;
    if (!current || event.pointerId !== current.pointerId) return;
    if (current.pointerType === 'touch') {
      current.moved ||= Math.hypot(event.clientX - current.startX, event.clientY - current.startY) > TAP_SLOP_PX;
      return;
    }
    if ((event.buttons & 1) === 0) {
      cancelGesture();
      return;
    }
    const index = hitItemIndex(event);
    if (index < 0 || !props.multiple) return;
    current.moved ||= index !== current.anchorIndex;
    current.endIndex = index;
  }

  /**
   * 左键释放时才由基线与最终范围计算并提交选择，派生 click 不再重复翻转。
   * @param {PointerEvent} event
   * @returns {void}
   */
  function onPointerUp(event) {
    const current = gesture.value;
    if (!current || event.pointerId !== current.pointerId) return;
    if (event.button !== 0) {
      cancelGesture();
      return;
    }
    // 悬停动画会改变命中区域；原地松手仍属于起始牌，不能因动画落空而丢失点击。
    const isTap = !current.moved && Math.hypot(
      event.clientX - current.startX,
      event.clientY - current.startY
    ) <= TAP_SLOP_PX;
    if (current.pointerType === 'touch' && !isTap) {
      cancelGesture();
      return;
    }
    const index = isTap ? current.anchorIndex : hitItemIndex(event);
    if ((!props.multiple && index !== current.anchorIndex) || (index < 0 && !current.moved)) {
      cancelGesture();
      return;
    }
    if (props.multiple && index >= 0) current.endIndex = index;
    const rangeIds = rangePreviewIds.value;
    const nextIds = props.multiple
      ? [
          ...current.baseline.filter((id) => !rangeIds.includes(id)),
          ...rangeIds.filter((id) => !current.baseline.includes(id))
        ]
      : current.removing ? [] : [props.items[current.anchorIndex].id];
    cancelGesture();
    input.changeSelection(nextIds);
  }

  /**
   * 只让当前指针的取消或捕获丢失终止手势。
   * @param {PointerEvent} event
   * @returns {void}
   */
  function onPointerCancel(event) {
    if (event.pointerId === gesture.value?.pointerId) cancelGesture();
  }

  /**
   * 保留辅助技术产生的无指针点击，忽略原生指针派生点击。
   * @param {object} item
   * @param {MouseEvent} event
   * @returns {void}
   */
  function onItemClick(item, event) {
    if (event.detail !== 0 || gesture.value || props.disabled || props.busy) return;
    if (!input.isItemSelectable(item)) {
      input.illegalSelection(item);
      return;
    }
    const selected = readSelection();
    input.changeSelection(selected.includes(item.id)
      ? selected.filter((id) => id !== item.id)
      : props.multiple ? [...selected, item.id] : [item.id]);
  }

  watch(
    () => JSON.stringify([
      props.items.map((item) => [item.id, Boolean(item.disabled)]),
      props.selectedItemIds,
      props.selectableItemIds,
      props.disabledItemIds,
      props.disabled,
      props.busy,
      props.multiple,
      props.selectionContext
    ]),
    cancelGesture,
    { flush: 'sync' }
  );
  onMounted(() => window.addEventListener('blur', cancelGesture));
  onBeforeUnmount(() => {
    window.removeEventListener('blur', cancelGesture);
    cancelGesture();
  });

  return { isSelecting, rangePreviewIds, onItemPointerDown, onPointerMove, onPointerUp, onPointerCancel, onItemClick };
}
