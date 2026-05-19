<template>
  <div class="user-menu-anchor" ref="anchor">
    <button
      type="button"
      class="user-menu-trigger"
      :aria-expanded="open ? 'true' : 'false'"
      aria-label="打开菜单"
      @click.stop="open = !open"
    >
      ▾
    </button>
    <div v-if="open" class="user-menu-panel" @click.stop>
      <button type="button" class="user-menu-item" @click="pick('ledger')">
        <span class="user-menu-label">积分信息</span>
        <span class="user-menu-value">{{ user.score || 0 }} / {{ user.totalScore || 0 }}</span>
      </button>
      <button type="button" class="user-menu-item" @click="pick('history')">历史对局</button>
      <button type="button" class="user-menu-item" @click="pick('propUsage')">道具使用记录</button>
      <button type="button" class="user-menu-item" @click="pick('purchase')">购买记录</button>
      <button type="button" class="user-menu-item" @click="pick('settings')">设置</button>
      <div class="user-menu-divider" />
      <button type="button" class="user-menu-item user-menu-item--bottom" :disabled="disableSwitch" @click="pick('user')">
        切换账户
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue';

defineProps({
  user: { type: Object, required: true },
  disableSwitch: { type: Boolean, default: false }
});

const emit = defineEmits(['open-modal']);

const open = ref(false);
const anchor = ref(null);

function pick(type) {
  open.value = false;
  emit('open-modal', type);
}

function onDocClick(e) {
  const root = anchor.value;
  if (root && root.contains(e.target)) {
    return;
  }
  open.value = false;
}

watch(open, (v) => {
  if (v) {
    setTimeout(() => document.addEventListener('click', onDocClick, true), 0);
  } else {
    document.removeEventListener('click', onDocClick, true);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, true);
});
</script>
