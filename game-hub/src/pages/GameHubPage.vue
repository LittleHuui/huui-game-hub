<template>
  <AppLayout>
    <template #top>
      <AppTopbar :user="user" :lock-nickname="sessionLocked" @update-nickname="onNicknameUpdate">
        <template #games>
          <GameSelector layout="topbar" />
        </template>
        <template #menu>
          <UserMenu :user="user" :disable-switch="sessionLocked" @open-modal="openModal" />
        </template>
      </AppTopbar>
    </template>

    <AppModal :visible="!!activeModal" :title="modalTitle" @close="closeModal">
      <template v-if="activeModal === 'user'">
        <div class="modal-actions">
          <input v-model="registerForm.username" placeholder="用户名" />
          <input v-model="registerForm.nickname" placeholder="昵称" />
          <button type="button" class="success" :disabled="sessionLocked" @click="createUser">创建用户</button>
        </div>
        <div class="user-list">
          <div
            v-for="u in userStore.users"
            :key="u.userId"
            class="user-card"
            :class="{ 'is-disabled': sessionLocked }"
            @click="switchUser(u.userId)"
          >
            <strong>{{ u.nickname }}</strong>
            <span class="user-name">（{{ u.username }}）</span>
            <span class="muted-small">总积分：{{ u.totalScore || 0 }}</span>
          </div>
        </div>
      </template>

      <template v-else-if="activeModal === 'history'">
        <div v-if="currentHistory.length === 0" class="empty-text">暂无历史对局</div>
        <div v-else class="history-list">
          <div v-for="(item, index) in currentHistory" :key="item.clientId || index" class="history-item">
            <strong>{{ historyResultText(item.result) }} · {{ diffLabel(item.difficulty) }}</strong>
            <span class="muted-small">
              用时：{{ item.time }} 秒 ｜ 得分：{{ item.score || 0 }} ｜ {{ formatDisplayTime(item.createdAt) }}
            </span>
            <div v-if="item.propUses && item.propUses.length" class="history-prop-line">
              本局道具：{{ formatPropUsesLine(item.propUses) }}
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="activeModal === 'propUsage'">
        <div v-if="propUsageRows.length === 0" class="empty-text">暂无道具使用记录</div>
        <div v-else class="log-list">
          <div v-for="(row, i) in propUsageRows" :key="row.clientId || i" class="log-item">
            <span class="muted-small">{{ formatDisplayTime(row.createdAt) }}</span>
            · {{ row.payload?.label || row.reason }}
            <span v-if="row.payload?.sessionId" class="muted-small">（对局 {{ row.payload.sessionId }}）</span>
          </div>
        </div>
      </template>

      <template v-else-if="activeModal === 'purchase'">
        <div v-if="purchaseRows.length === 0" class="empty-text">暂无购买记录</div>
        <div v-else class="log-list">
          <div v-for="(row, i) in purchaseRows" :key="row.clientId || i" class="log-item">
            <span class="muted-small">{{ formatDisplayTime(row.createdAt) }}</span>
            · {{ row.payload?.label || '购买' }} · 花费 {{ row.payload?.cost ?? 0 }} 积分
          </div>
        </div>
      </template>

      <template v-else-if="activeModal === 'ledger'">
        <div v-if="ledgerRows.length === 0" class="empty-text">暂无积分流水</div>
        <div v-else class="log-list">
          <div v-for="(row, i) in ledgerRows" :key="row.clientId || i" class="log-item">
            <span class="muted-small">{{ formatDisplayTime(row.createdAt) }}</span>
            · {{ row.reason }}
            <strong :style="{ color: row.type === 'gain' ? '#6ee7b7' : '#fca5a5' }">
              {{ row.type === 'gain' ? '+' : '-' }}{{ row.amount }}
            </strong>
            ｜ 余额 {{ walletAfter(row) }}
          </div>
        </div>
      </template>

      <template v-else-if="activeModal === 'settings'">
        <div class="settings-row">
          <div class="settings-row-text">
            <strong>数据模式</strong>
            <p>自动模式会探测接口并优先使用远程数据，失败时降级为本地缓存；本地模式仅读写本机；接口模式仅走远程，失败会报错。</p>
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px; align-items: flex-start">
            <label class="checkbox-row" style="margin-top: 0">
              <input type="radio" name="repoMode" value="auto" :checked="repositoryModeModel === 'auto'" @change="setRepositoryMode('auto')" />
              <span>自动模式（推荐）</span>
            </label>
            <label class="checkbox-row" style="margin-top: 0">
              <input type="radio" name="repoMode" value="local" :checked="repositoryModeModel === 'local'" @change="setRepositoryMode('local')" />
              <span>本地模式</span>
            </label>
            <label class="checkbox-row" style="margin-top: 0" :class="{ 'is-disabled': !repositoryRemoteEnabled }">
              <input
                type="radio"
                name="repoMode"
                value="remote"
                :disabled="!repositoryRemoteEnabled"
                :checked="repositoryModeModel === 'remote'"
                @change="setRepositoryMode('remote')"
              />
              <span>接口模式（需接口可用）</span>
            </label>
          </div>
        </div>
        <div class="settings-row">
          <div class="settings-row-text">
            <strong>数字格邻居高亮</strong>
            <p>鼠标悬停在已翻开且带数字的格子上时，为周围 8 格叠加浅色描边。</p>
          </div>
          <label class="settings-toggle">
            <input type="checkbox" :checked="neighborHoverRingEnabled" @change="setNeighborHoverRingPref($event.target.checked)" />
          </label>
        </div>
      </template>
    </AppModal>

    <UserLoginModal :visible="platform.bootStatus === 'waitingLogin'" @success="onLoginSuccess" />

    <div class="gh-game-shell" :class="{ 'gh-game-shell--locked': !platform.isPlayable }">
      <router-view v-slot="{ Component }">
        <component :is="Component" ref="gamePageRef" />
      </router-view>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, reactive, computed, provide, watch } from 'vue';
import AppLayout from '../components/AppLayout.vue';
import AppTopbar from '../components/AppTopbar.vue';
import AppModal from '../components/AppModal.vue';
import UserMenu from '../components/UserMenu.vue';
import GameSelector from '../components/GameSelector.vue';
import UserLoginModal from '../components/UserLoginModal.vue';
import { GH_MINESWEEPER_SESSION_LOCK, GH_OPEN_HUB_MODAL } from '../constants/injectionKeys.js';
import { createGameSession } from '../services/gameSessionService.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { useUserStore } from '../stores/userStore.js';
import { useWalletStore } from '../stores/walletStore.js';
import { useInventoryStore } from '../stores/inventoryStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import { MINESWEEPER_PRESETS } from '../games/minesweeper/minesweeperConfig.js';
import { formatDisplayTime } from '../utils/formatTime.js';
import * as userService from '../services/userService.js';
import * as walletService from '../services/walletService.js';
import * as toastService from '../services/toastService.js';

const platform = usePlatformStore();
const session = createGameSession({ gameCode: () => platform.currentGameCode });
const userStore = useUserStore();
const walletStore = useWalletStore();
const inventoryStore = useInventoryStore();
const historyStore = useHistoryStore();
const settingStore = useSettingStore();

const user = session.currentUser;
const sessionLocked = ref(false);
const gamePageRef = ref(null);

const registerForm = reactive({ username: '', nickname: '' });
const activeModal = ref('');

const repositoryModeModel = computed(() => settingStore.settings.repositoryMode || 'auto');
const repositoryRemoteEnabled = computed(() => platform.remoteAvailable);
const neighborHoverRingEnabled = computed(() => user.value.prefs?.neighborHoverRing !== false);

const currentHistory = computed(() => {
  const uid = userStore.auth.currentUserId;
  const list = historyStore.matchesForUser(uid);
  return list.slice().reverse();
});

const propUsageRows = computed(() => {
  const uid = userStore.auth.currentUserId;
  const fromRemote = historyStore.propUsageForUser(uid);
  if (fromRemote.length > 0) {
    return fromRemote.slice().reverse();
  }
  return inventoryStore
    .listForUser(uid)
    .filter((r) => r.reason === 'use')
    .slice()
    .reverse();
});

const purchaseRows = computed(() => {
  const uid = userStore.auth.currentUserId;
  return historyStore.purchasesForUser(uid).slice().reverse();
});

const ledgerRows = computed(() => {
  const uid = userStore.auth.currentUserId;
  return walletStore.listForUser(uid).slice().reverse();
});

const modalTitle = computed(() => {
  const map = {
    history: '历史对局',
    propUsage: '道具使用记录',
    purchase: '道具购买记录',
    ledger: '积分流水',
    settings: '显示与数据设置',
    user: '切换或创建用户'
  };
  return map[activeModal.value] || '';
});

provide(GH_MINESWEEPER_SESSION_LOCK, {
  setLocked(locked) {
    sessionLocked.value = !!locked;
  }
});

function openModal(type) {
  if (type === 'user' && sessionLocked.value) {
    toastService.push('对局进行中，无法切换或创建用户', 'warning');
    return;
  }
  activeModal.value = type;
  userService.refreshModalData(type);
}

provide(GH_OPEN_HUB_MODAL, openModal);

function closeModal() {
  activeModal.value = '';
}

function walletAfter(row) {
  return walletService.balanceAfterLedgerRow(row);
}

function historyResultText(result) {
  const m = { win: '胜利', fail: '失败', end: '主动结束' };
  return m[result] || '未知结果';
}

function diffLabel(value) {
  const preset = MINESWEEPER_PRESETS[value];
  return preset?.label || '未知难度';
}

function formatPropUsesLine(list) {
  if (!list || !list.length) {
    return '无';
  }
  return list.map((v) => v.label || v.type).join('；');
}

async function setRepositoryMode(mode) {
  await userService.setRepositoryMode(mode);
}

async function setNeighborHoverRingPref(value) {
  await userService.setNeighborHoverRing(value);
  if (!value) {
    gamePageRef.value?.clearNeighborRing?.();
  }
}

async function createUser() {
  const ok = await userService.createUser({
    username: registerForm.username,
    nickname: registerForm.nickname
  });
  if (ok) {
    registerForm.username = '';
    registerForm.nickname = '';
    closeModal();
  }
}

function switchUser(userId) {
  if (userService.switchUser(userId, sessionLocked.value)) {
    closeModal();
  }
}

async function onNicknameUpdate(name) {
  await userService.updateNickname(name);
}

/**
 * 登录/创建成功（状态由 boot 流程更新为 ready）。
 */
function onLoginSuccess() {
  /* 弹窗通过 bootStatus 自动关闭 */
}

watch(
  () => platform.currentGameCode,
  () => {
    sessionLocked.value = false;
  }
);
</script>

<style scoped>
.gh-game-shell {
  position: relative;
}

.gh-game-shell--locked {
  pointer-events: none;
  opacity: 0.55;
  filter: grayscale(0.08);
}
</style>
