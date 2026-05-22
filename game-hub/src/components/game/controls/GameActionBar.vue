<template>
  <div class="game-action-bar" :class="extraClass">
    <button
      v-for="item in visibleActions"
      :key="item.key"
      type="button"
      class="side-action game-action-btn"
      :class="resolveButtonClasses(item)"
      :disabled="item.disabled"
      @click="onAction(item.key)"
    >
      {{ item.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { GAME_ACTION_SIZE, GAME_ACTION_TYPE } from './gameControlEnums.js';

const props = defineProps({
  /** @type {import('vue').PropType<Array<{ key: string; label: string; type?: string; size?: string; visible?: boolean; disabled?: boolean; extraClass?: string }>>} */
  actions: {
    type: Array,
    default: () => []
  },
  extraClass: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['action']);

/**
 * 过滤出需要展示的操作项。
 */
const visibleActions = computed(() =>
  (props.actions || []).filter((item) => item && item.visible !== false)
);

/**
 * 将操作类型/尺寸映射为枚举 CSS；extraClass 仅作附加扩展样式。
 * @param {{ type?: string; size?: string; extraClass?: string }} item
 * @returns {string[]}
 */
function resolveButtonClasses(item) {
  const classes = [];
  const type = item.type || GAME_ACTION_TYPE.PRIMARY;
  const size = item.size || GAME_ACTION_SIZE.MD;
  if (Object.values(GAME_ACTION_TYPE).includes(type)) {
    classes.push(`game-action-btn--${type}`);
  }
  if (Object.values(GAME_ACTION_SIZE).includes(size)) {
    classes.push(`game-action-btn--${size}`);
  }
  if (item.extraClass) {
    classes.push(item.extraClass);
  }
  return classes;
}

/**
 * 向父组件上报操作 key。
 * @param {string} key
 */
function onAction(key) {
  emit('action', key);
}
</script>
