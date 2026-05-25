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
      <svg class="online-users-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M9 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-3.3 0-6 1.7-6 3.8V20h12v-2.2C15 15.7 12.3 14 9 14Zm7.5-1.4a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm.5 1.5c-.7 0-1.4.1-2 .3 1.2.9 2 2.1 2 3.4V20h4v-1.8c0-2.2-1.8-4.1-4-4.1Z"
          fill="currentColor"
        />
      </svg>
      <span v-if="onlineCount > 0" class="online-users-badge">{{ onlineCount }}</span>
    </button>

    <div v-if="open" class="online-users-panel" @click.stop>
      <div class="online-users-head">
        <div>
          <strong>在线用户</strong>
          <span class="online-users-subtitle">{{ canRefreshOnlineUsers ? '仅展示昵称和在线时长' : '本地模式不刷新在线用户' }}</span>
        </div>
        <button type="button" class="online-users-refresh" :disabled="loading || !canRefreshOnlineUsers" @click="refreshUsers">
          刷新
        </button>
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
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
  if (!canRefreshOnlineUsers.value || loading.value) {
    return;
  }
  loading.value = true;
  errorMessage.value = '';
  try {
    const list = await onlineService.loadOnlineUsers({ silent: true, throwOnError: true });
    users.value = list.map(toDisplayUser);
    nowTick.value = Date.now();
  } catch {
    errorMessage.value = '在线用户加载失败，请稍后重试';
  } finally {
    loading.value = false;
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

/**
 * 处理外部点击关闭。
 * @param {MouseEvent} e
 */
function onDocClick(e) {
  const root = anchor.value;
  if (root && root.contains(e.target)) {
    return;
  }
  open.value = false;
}

watch(open, (value) => {
  if (value) {
    if (!canRefreshOnlineUsers.value) {
      open.value = false;
      return;
    }
    loadUsers();
    setTimeout(() => document.addEventListener('click', onDocClick, true), 0);
  } else {
    document.removeEventListener('click', onDocClick, true);
  }
});

watch(canRefreshOnlineUsers, (value) => {
  if (value) {
    loadUsers();
    startTimers();
    return;
  }
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
  stopTimers();
  document.removeEventListener('click', onDocClick, true);
});
</script>

<style scoped>
.online-users-dropdown {
  position: relative;
}

.online-users-trigger {
  position: relative;
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(248, 250, 252, 0.88);
  transform: none;
}

.online-users-trigger:hover {
  background: rgba(59, 130, 246, 0.38);
  border-color: rgba(148, 163, 184, 0.45);
  color: #f8fafc;
}

.online-users-trigger.is-disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.online-users-icon {
  width: 20px;
  height: 20px;
}

.online-users-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #22c55e;
  color: #052e16;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
}

.online-users-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  width: min(320px, calc(100vw - 16px));
  padding: 12px;
  border-radius: 14px;
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.16);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4);
  z-index: 230;
}

.online-users-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.online-users-subtitle {
  display: block;
  margin-top: 3px;
  color: rgba(226, 232, 240, 0.68);
  font-size: 12px;
  font-weight: 400;
}

.online-users-refresh {
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.18);
  border: 1px solid rgba(125, 211, 252, 0.28);
  color: #e0f2fe;
  font-size: 12px;
  transform: none;
}

.online-users-refresh:disabled {
  opacity: 0.55;
  cursor: wait;
}

.online-users-state {
  padding: 18px 8px;
  color: rgba(226, 232, 240, 0.78);
  text-align: center;
  font-size: 13px;
}

.online-users-state--error {
  color: #fecaca;
}

.online-users-list {
  display: flex;
  max-height: 280px;
  overflow-y: auto;
  flex-direction: column;
  gap: 6px;
}

.online-users-row {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.05);
}

.online-users-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(125, 211, 252, 0.18);
  color: #bae6fd;
  font-size: 13px;
  font-weight: 700;
  line-height: 28px;
  text-align: center;
}

.online-users-name {
  min-width: 0;
  overflow: hidden;
  color: #f8fafc;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.online-users-duration {
  color: rgba(226, 232, 240, 0.72);
  font-size: 12px;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .online-users-panel {
    width: min(300px, calc(100vw - 12px));
  }
}
</style>
