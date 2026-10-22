<template>
  <div ref="anchor" class="online-users-dropdown">
    <button
      type="button"
      class="online-users-trigger"
      :class="{ 'is-disabled': !canRefreshOnlineUsers }"
      :aria-expanded="open ? 'true' : 'false'"
      :disabled="!canRefreshOnlineUsers"
      aria-label="查看在线用户"
      :title="canRefreshOnlineUsers ? '在线用户' : '本地模式不显示在线用户'"
      @click.stop="toggleOpen"
    >
      <AppIcon name="users" :size="18" />
      <span v-if="onlineCount > 0" class="online-users-badge">{{ onlineCount }}</span>
    </button>

    <div v-if="open" v-viewport-backdrop class="online-users-backdrop" @click="open = false" />
    <div v-if="open" class="online-users-panel" @click.stop @keydown.esc="open = false">
      <div class="online-users-head">
        <div>
          <strong>在线用户</strong>

        </div>
        <button type="button" class="online-users-refresh" :disabled="loading || !canRefreshOnlineUsers" @click="refreshUsers">
          <AppIcon name="refresh" :size="16" /><span>刷新</span>
        </button>
        <button class="online-users-close" type="button" aria-label="关闭在线用户" @click="open = false"><AppIcon name="close" :size="16" /></button>
      </div>

      <div v-if="loading && users.length === 0" class="online-users-state">正在加载在线用户...</div>
      <div v-else-if="errorMessage" class="online-users-state online-users-state--error">
        {{ errorMessage }}
      </div>
      <div v-else-if="displayUsers.length === 0" class="online-users-state">暂无在线用户</div>
      <div v-else class="online-users-list hub-scrollbar">
        <div v-for="(user, index) in displayUsers" :key="index" class="online-users-row">
          <span class="online-users-avatar" aria-hidden="true">{{ user.nickname.charAt(0) }}</span>
          <span class="online-users-name">{{ user.nickname }}</span>
          <span class="online-users-duration">{{ user.durationText }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import AppIcon from '../ui/AppIcon.vue';
import vViewportBackdrop from '../ui/viewportBackdrop.js';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useOutsideClick } from '../../composables/useOutsideClick.js';
import * as onlineService from '../../services/onlineService.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import { useSettingStore } from '../../stores/settingStore.js';

const DISPLAY_REFRESH_INTERVAL_MS = 60 * 1000;
const LIST_REFRESH_INTERVAL_MS = 30 * 1000;

const open = ref(false);
const loading = ref(false);
const errorMessage = ref('');
const users = ref([]);
const nowTick = ref(Date.now());
const anchor = ref(null);
const platformStore = usePlatformStore();
const settingStore = useSettingStore();

let requestGeneration = 0;
let disposed = false;
let displayTimer = null;
let onlineUsersRefreshTimer = null;

const onlineCount = computed(() => users.value.length);
const canRefreshOnlineUsers = computed(() => (
  settingStore.settings.repositoryMode !== 'local' &&
  (platformStore.networkMode === 'online' || platformStore.networkMode === 'degraded')
));
const displayUsers = computed(() => {
  const now = nowTick.value;
  return users.value.map((user) => ({
    ...user,
    durationText: formatOnlineDuration(user.onlineAt, now)
  }));
});

/**
 * 切换在线用户面板。
 */
function toggleOpen() {
  if (!canRefreshOnlineUsers.value) {
    return;
  }
  open.value = !open.value;
}

/**
 * 手动刷新在线用户列表。
 * @returns {Promise<void>}
 */
async function refreshUsers() {
  if (!canRefreshOnlineUsers.value) {
    return;
  }
  await loadUsers();
}

/**
 * 加载在线用户列表。
 * @returns {Promise<void>}
 */
async function loadUsers() {
  if (disposed || !canRefreshOnlineUsers.value || loading.value) {
    return;
  }
  const generation = ++requestGeneration;
  const isCurrent = () => !disposed && generation === requestGeneration && canRefreshOnlineUsers.value;
  loading.value = true;
  errorMessage.value = '';
  try {
    const list = await onlineService.loadOnlineUsers({ silent: true, throwOnError: true });
    if (!isCurrent()) return;
    users.value = list.map(toDisplayUser);
    nowTick.value = Date.now();
  } catch {
    if (isCurrent()) errorMessage.value = '在线用户加载失败，请稍后重试';
  } finally {
    if (isCurrent()) loading.value = false;
  }
}

/**
 * 转换为仅用于展示的安全字段。
 * @param {object} user
 * @returns {{ nickname: string, onlineAt: number|null }}
 */
function toDisplayUser(user) {
  const nickname = typeof user?.nickname === 'string' && user.nickname.trim() ? user.nickname.trim() : '匿名玩家';
  const onlineAt = Number.isFinite(Number(user?.onlineAt)) ? Number(user.onlineAt) : null;
  return { nickname, onlineAt };
}

/**
 * 基于 onlineAt 格式化在线时长。
 * @param {number|null} onlineAt
 * @param {number} now
 * @returns {string}
 */
function formatOnlineDuration(onlineAt, now) {
  if (!Number.isFinite(onlineAt)) {
    return '在线时长未知';
  }
  const minutes = Math.max(0, Math.floor((now - onlineAt) / 60000));
  if (minutes < 1) {
    return '刚刚在线';
  }
  if (minutes < 60) {
    return `在线 ${minutes} 分钟`;
  }
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  return restMinutes > 0 ? `在线 ${hours} 小时 ${restMinutes} 分钟` : `在线 ${hours} 小时`;
}

/**
 * 启动展示与在线用户刷新定时器。
 */
function startTimers() {
  if (displayTimer === null) {
    displayTimer = window.setInterval(() => {
      nowTick.value = Date.now();
    }, DISPLAY_REFRESH_INTERVAL_MS);
  }
  startOnlineUsersRefresh();
}

/**
 * 启动在线用户刷新定时器。
 */
function startOnlineUsersRefresh() {
  if (!canRefreshOnlineUsers.value || onlineUsersRefreshTimer !== null) {
    return;
  }
  onlineUsersRefreshTimer = window.setInterval(() => {
    loadUsers();
  }, LIST_REFRESH_INTERVAL_MS);
}

/**
 * 停止展示与在线用户刷新定时器。
 */
function stopTimers() {
  if (displayTimer !== null) {
    window.clearInterval(displayTimer);
    displayTimer = null;
  }
  stopOnlineUsersRefresh();
}

/**
 * 停止在线用户刷新定时器。
 */
function stopOnlineUsersRefresh() {
  if (onlineUsersRefreshTimer !== null) {
    window.clearInterval(onlineUsersRefreshTimer);
    onlineUsersRefreshTimer = null;
  }
}

useOutsideClick(open, anchor, () => { open.value = false; });
watch(open, (visible) => {
  if (visible && canRefreshOnlineUsers.value) void loadUsers();
});

watch(canRefreshOnlineUsers, (value) => {
  if (value) {
    loadUsers();
    startTimers();
    return;
  }
  requestGeneration += 1;
  loading.value = false;
  open.value = false;
  users.value = [];
  errorMessage.value = '';
  stopTimers();
});

onMounted(() => {
  if (canRefreshOnlineUsers.value) {
    loadUsers();
    startTimers();
  }
});

onBeforeUnmount(() => {
  disposed = true;
  requestGeneration += 1;
  stopTimers();
});
</script>
