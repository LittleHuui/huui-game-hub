<template>
  <article
    class="turn-player-panel"
    :class="panelClassList"
  >
    <div class="turn-player-panel__shell">
      <div class="turn-player-panel__avatar-wrap">
        <div class="turn-player-panel__avatar" :title="nickname">
          <img v-if="avatarUrl" :src="avatarUrl" :alt="nickname" />
          <span v-else aria-hidden="true">{{ avatarInitial }}</span>
        </div>
        <span v-if="statusBadgeText" class="turn-player-panel__badge" :class="statusBadgeClass">
          {{ statusBadgeText }}
        </span>
        <span
          v-if="isSpectator && !statusBadgeText"
          class="turn-player-panel__badge turn-player-panel__badge--spectator"
        >
          观战
        </span>
        <span v-if="finishRankLabel" class="turn-player-panel__rank-badge">
          {{ finishRankLabel }}
        </span>
      </div>

      <div class="turn-player-panel__info">
        <h3 class="turn-player-panel__name" :title="nickname">{{ nickname }}</h3>
        <p v-if="handCount != null" class="turn-player-panel__stat">
          手牌 {{ handCount }}
          <span
            v-if="showLowHandCountLabel"
            class="turn-player-panel__low-hand-tag"
          >
            {{ lowHandCountLabel }}
          </span>
        </p>
        <p v-if="lastAction" class="turn-player-panel__last-action" :title="lastAction">
          {{ lastAction }}
        </p>
      </div>

      <div class="turn-player-panel__countdown-slot">
        <TurnCountdown
          v-if="showCountdown"
          :seconds="countdownSeconds"
          :expires-at-ms="countdownExpiresAtMs"
          compact
        />
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue';
import TurnCountdown from '../controls/TurnCountdown.vue';
import '../controls/turnGame.css';

const props = defineProps({
  nickname: {
    type: String,
    default: '玩家'
  },
  avatar: {
    type: String,
    default: ''
  },
  handCount: {
    type: Number,
    default: null
  },
  lastAction: {
    type: String,
    default: ''
  },
  isAi: {
    type: Boolean,
    default: false
  },
  isManaged: {
    type: Boolean,
    default: false
  },
  isSpectator: {
    type: Boolean,
    default: false
  },
  isCurrentTurn: {
    type: Boolean,
    default: false
  },
  finishRank: {
    type: Number,
    default: null
  },
  layout: {
    type: String,
    default: 'edge-left',
    validator: (value) => ['edge-left', 'edge-right'].includes(value)
  },
  countdownSeconds: {
    type: Number,
    default: null
  },
  countdownExpiresAtMs: {
    type: Number,
    default: null
  },
  showCountdown: {
    type: Boolean,
    default: false
  },
  lowHandCountLabel: {
    type: String,
    default: ''
  }
});

const avatarUrl = computed(() => String(props.avatar || '').trim());

const avatarInitial = computed(() => {
  const name = String(props.nickname || '').trim();
  return name ? name.charAt(0) : '?';
});

const statusBadgeText = computed(() => {
  if (props.isAi) {
    return 'AI';
  }
  if (props.isManaged) {
    return '托管';
  }
  return '';
});

const statusBadgeClass = computed(() => {
  if (props.isAi) {
    return 'turn-player-panel__badge--ai';
  }
  if (props.isManaged) {
    return 'turn-player-panel__badge--managed';
  }
  return '';
});

const finishRankLabel = computed(() => {
  const rank = Number(props.finishRank);
  if (!Number.isFinite(rank) || rank <= 0) {
    return '';
  }
  return `第${rank}名`;
});

const showLowHandCountLabel = computed(() => {
  const label = String(props.lowHandCountLabel || '').trim();
  if (!label) {
    return false;
  }
  return Number(props.handCount) === 1;
});

const panelClassList = computed(() => ({
  'turn-player-panel--active': props.isCurrentTurn,
  'turn-player-panel--spectator': props.isSpectator,
  'turn-player-panel--edge-left': props.layout === 'edge-left',
  'turn-player-panel--edge-right': props.layout === 'edge-right'
}));
</script>
