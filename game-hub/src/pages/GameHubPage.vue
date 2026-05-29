<template>
  <AppLayout>
    <template #top>
      <AppTopbar :user="user" :lock-nickname="sessionLocked" @update-nickname="onNicknameUpdate">
        <template #games>
          <GameSelector layout="topbar" />
        </template>
        <template #menu>
          <UserMenu :user="user" :disable-switch="sessionLocked" @open-modal="openModal" />
          <OnlineUsersDropdown />
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
        <div v-else class="history-list hub-scrollbar">
          <div v-for="(item, index) in currentHistory" :key="item.clientId || index" class="history-item">
            <strong>{{ matchGameLabel(item) }} · {{ historyResultText(item.result) }} · {{ diffLabel(item) }}</strong>
            <span class="muted-small">
              用时：{{ formatHistoryDuration(item.durationMs) }} ｜ 得分：{{ item.score || 0 }} ｜ {{ formatDisplayTime(item.createdAt) }}
            </span>
            <div v-if="item.propUses && item.propUses.length" class="history-prop-line">
              本局道具：{{ formatPropUsesLine(item.propUses) }}
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="activeModal === 'propUsage'">
        <div v-if="propUsageRows.length === 0" class="empty-text">暂无道具使用记录</div>
        <div v-else class="log-list hub-scrollbar">
          <div v-for="(row, i) in propUsageRows" :key="row.clientId || i" class="log-item">
            <span class="muted-small">{{ formatDisplayTime(row.createdAt) }}</span>
            · {{ row.payload?.label || row.reason }}
            <span v-if="row.payload?.sessionId" class="muted-small">（对局 {{ row.payload.sessionId }}）</span>
          </div>
        </div>
      </template>

      <template v-else-if="activeModal === 'purchase'">
        <div v-if="purchaseRows.length === 0" class="empty-text">暂无购买记录</div>
        <div v-else class="log-list hub-scrollbar">
          <div v-for="(row, i) in purchaseRows" :key="row.clientId || i" class="log-item">
            <span class="muted-small">{{ formatDisplayTime(row.createdAt) }}</span>
            · {{ purchaseRecordLabel(row) }} · 花费 {{ row.payload?.cost ?? 0 }} 积分
          </div>
        </div>
      </template>

      <template v-else-if="activeModal === 'ledger'">
        <div v-if="ledgerRows.length === 0" class="empty-text">暂无积分流水</div>
        <div v-else class="log-list hub-scrollbar">
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
        <section v-for="group in hubGameSettingGroups" :key="group.gameCode" class="settings-game-group">
          <h3 class="settings-game-title">{{ group.gameName }}</h3>
          <div
            v-for="item in group.items"
            :key="`${group.gameCode}.${item.key}`"
            class="settings-row settings-row--nested"
          >
            <div class="settings-row-text">
              <strong>{{ item.label }}</strong>
              <p v-if="item.description">{{ item.description }}</p>
            </div>
            <label class="settings-toggle">
              <input
                type="checkbox"
                :checked="Boolean(item.value)"
                @change="onHubGameSettingChange(item.gameCode, item.key, $event.target.checked)"
              />
            </label>
          </div>
        </section>
      </template>
    </AppModal>

    <UserLoginModal :visible="platform.bootStatus === 'waitingLogin'" @success="onLoginSuccess" />

    <RoomInviteConfirmDialog
      :visible="Boolean(pendingInvite)"
      :room-name="pendingInvite?.roomName || '房间'"
      :inviter-nickname="pendingInvite?.inviterNickname || '玩家'"
      :submitting="inviteActionSubmitting"
      :error-message="inviteActionError"
      @accept="acceptInvite"
      @reject="rejectInvite"
    />

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
import OnlineUsersDropdown from '../components/game-hub/OnlineUsersDropdown.vue';
import GameSelector from '../components/GameSelector.vue';
import UserLoginModal from '../components/UserLoginModal.vue';
import RoomInviteConfirmDialog from '../components/game-hub/room/RoomInviteConfirmDialog.vue';
import { useGlobalRoomInvite } from '../composables/useGlobalRoomInvite.js';
import { GH_OPEN_HUB_MODAL } from '../constants/injectionKeys.js';
import { createGameSession } from '../services/gameSessionService.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { useUserStore } from '../stores/userStore.js';
import { useWalletStore } from '../stores/walletStore.js';
import { useInventoryStore } from '../stores/inventoryStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import { getDifficultyName } from '../services/gameDifficultyService.js';
import { resolveGameDisplayName } from '../services/gameCatalogService.js';
import { resolveMatchGameCode } from '../mappers/matchMapper.js';
import { formatDisplayTime } from '../utils/formatTime.js';
import { resolvePropDisplayName } from '../utils/resolvePropDisplayName.js';
import { recentHistoryRecords } from '../utils/historySort.js';
import * as userService from '../services/userService.js';
import * as walletService from '../services/walletService.js';
import * as toastService from '../services/toastService.js';
import { buildHubGameSettingGroups, setHubGameSettingSwitch } from '../services/gameSettingService.js';

const platform = usePlatformStore();
const {
  pendingInvite,
  inviteActionSubmitting,
  inviteActionError,
  rejectInvite,
  acceptInvite
} = useGlobalRoomInvite();
const session = createGameSession({ gameCode: () => platform.currentGameCode });
const userStore = useUserStore();
const walletStore = useWalletStore();
const inventoryStore = useInventoryStore();
const historyStore = useHistoryStore();
const settingStore = useSettingStore();

const user = session.currentUser;
const sessionLocked = computed(() => platform.gameSwitchLocked);
const gamePageRef = ref(null);

const registerForm = reactive({ username: '', nickname: '' });
const activeModal = ref('');

const repositoryModeModel = computed(() => settingStore.settings.repositoryMode || 'auto');
const repositoryRemoteEnabled = computed(() => platform.remoteAvailable);
/** 顶栏设置：统一定义列表，与当前路由游戏无关 */
const hubGameSettingGroups = computed(() => {
  const u = userStore.currentUser;
  if (u?.gameSettings) {
    void u.gameSettings;
  }
  return buildHubGameSettingGroups();
});

const currentHistory = computed(() => {
  const uid = userStore.auth.currentUserId;
  return historyStore.matchesForUser(uid);
});

const propUsageRows = computed(() => {
  const uid = userStore.auth.currentUserId;
  const fromRemote = historyStore.propUsageForUser(uid);
  if (fromRemote.length > 0) {
    return fromRemote;
  }
  return recentHistoryRecords(
    inventoryStore.listForUser(uid).filter((r) => r.reason === 'use'),
    50
  );
});

const purchaseRows = computed(() => {
  const uid = userStore.auth.currentUserId;
  return historyStore.purchasesForUser(uid);
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

/**
 * 历史条目游戏展示名。
 * @param {object} item
 * @returns {string}
 */
function matchGameLabel(item) {
  const code = resolveMatchGameCode(item);
  const name = resolveGameDisplayName(code);
  return name || code || '未知游戏';
}

/**
 * 历史条目难度展示名。
 * @param {object} item
 * @returns {string}
 */
function diffLabel(item) {
  const gameCode = resolveMatchGameCode(item);
  if (!gameCode) {
    return item?.difficultyCode || '—';
  }
  return getDifficultyName(gameCode, item?.difficultyCode);
}

/**
 * 购买记录道具展示名。
 * @param {object} row
 * @returns {string}
 */
function purchaseRecordLabel(row) {
  const propCode = row?.propCode || row?.payload?.propCode || '';
  const gameCode = row?.gameCode || '';
  const name = resolvePropDisplayName(propCode, gameCode);
  return name || '购买';
}

function formatHistoryDuration(durationMs) {
  if (durationMs != null && Number.isFinite(durationMs)) {
    return `${(durationMs / 1000).toFixed(1)} 秒`;
  }
  return '—';
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

/**
 * 顶栏游戏设置开关变更（按 gameCode + settingKey 持久化）。
 * @param {string} gameCode
 * @param {string} key
 * @param {boolean} value
 */
async function onHubGameSettingChange(gameCode, key, value) {
  await setHubGameSettingSwitch(gameCode, key, value);
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
    platform.unlockGameSwitch();
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

.settings-game-group {
  margin-top: 8px;
}

.settings-game-group:first-of-type {
  margin-top: 4px;
}

.settings-game-title {
  margin: 0 0 4px;
  padding: 8px 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.88);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.settings-row--nested {
  padding-left: 8px;
}
</style>
