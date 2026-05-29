<template>
  <section class="uno-game-view game-card">
    <header class="uno-game-view__head">
      <h2 class="game-card__title">对局视图</h2>
      <p v-if="animationHint" class="muted-small uno-game-view__hint">播放事件：{{ animationHint }}</p>
      <p class="muted-small uno-game-view__meta">版本 {{ version }} · 视角 {{ viewerPlayerId || '—' }}</p>
    </header>

    <div class="uno-game-view__zones">
      <div class="uno-game-view__zone">
        <h3 class="uno-game-view__zone-title">公开区 publicState</h3>
        <div v-if="discardCardCode" class="uno-game-view__discard">
          <UnoCard :card-code="discardCardCode" show-code />
        </div>
        <p v-else class="empty-text">暂无弃牌顶</p>
        <ul v-if="publicPlayers.length" class="uno-game-view__players">
          <li v-for="player in publicPlayers" :key="player.playerId" class="uno-game-view__player">
            <span>{{ player.nickname || player.playerId }}</span>
            <span class="muted-small">手牌 {{ player.handCount }}</span>
          </li>
        </ul>
      </div>

      <div class="uno-game-view__zone">
        <h3 class="uno-game-view__zone-title">私有区 privateState</h3>
        <div v-if="handCardCodes.length" class="uno-page__cards">
          <UnoCard
            v-for="code in handCardCodes"
            :key="code"
            :card-code="code"
            show-code
          />
        </div>
        <p v-else class="empty-text">暂无手牌</p>
      </div>
    </div>

    <div class="uno-game-view__actions">
      <h3 class="uno-game-view__zone-title">合法操作 legalActions</h3>
      <div v-if="legalActions.length" class="uno-game-view__action-list">
        <button
          v-for="action in legalActions"
          :key="action.actionKey"
          type="button"
          class="game-action-btn game-action-btn--secondary game-action-btn--sm"
          :disabled="actionsDisabled"
          @click="emitAction(action)"
        >
          {{ formatActionLabel(action) }}
        </button>
      </div>
      <p v-else class="empty-text">当前无可执行操作</p>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import UnoCard from './UnoCard.vue';

const props = defineProps({
  version: {
    type: Number,
    default: 0
  },
  viewerPlayerId: {
    type: String,
    default: ''
  },
  publicState: {
    type: Object,
    default: () => ({})
  },
  privateState: {
    type: Object,
    default: () => ({})
  },
  legalActions: {
    type: Array,
    default: () => []
  },
  animationHint: {
    type: String,
    default: ''
  },
  actionsDisabled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['action']);

const discardCardCode = computed(() => {
  const top = props.publicState?.discardTopCard;
  if (!top || typeof top !== 'object') {
    return '';
  }
  return String(top.cardCode || top.code || '').trim();
});

const publicPlayers = computed(() => {
  const list = props.publicState?.players;
  if (!Array.isArray(list)) {
    return [];
  }
  return list.map((item) => ({
    playerId: String(item?.playerId || '').trim(),
    nickname: String(item?.nickname || '').trim(),
    handCount: Number(item?.handCount) || 0
  }));
});

const handCardCodes = computed(() => {
  const list = props.privateState?.handCards;
  if (!Array.isArray(list)) {
    return [];
  }
  return list
    .map((item) => {
      if (typeof item === 'string') {
        return item.trim();
      }
      if (item && typeof item === 'object') {
        return String(item.cardCode || item.code || '').trim();
      }
      return '';
    })
    .filter(Boolean);
});

/**
 * @param {object} action
 * @returns {string}
 */
function formatActionLabel(action) {
  const type = String(action?.actionType || '').trim();
  const key = String(action?.actionKey || '').trim();
  return key ? `${type} (${key})` : type || '操作';
}

/**
 * @param {object} action
 */
function emitAction(action) {
  emit('action', action);
}
</script>
