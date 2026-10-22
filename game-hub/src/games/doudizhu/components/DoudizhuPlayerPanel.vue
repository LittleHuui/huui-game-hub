<template>
  <article
    class="doudizhu-player-panel"
    :class="panelClassList"
  >
    <TurnPlayerPanel :nickname="nickname" :avatar="isAi ? botAvatarUrl : ''" :hand-count="handCount"
      :is-current-turn="isCurrentTurn" :is-ai="isAi" :managed-label="managedLabel" :managed-badge-class="managedBadgeClass"
      :show-countdown="showCountdown" :countdown-seconds="countdownSeconds" :countdown-expires-at-ms="countdownExpiresAtMs"
      :layout="layout === 'right' ? 'edge-right' : 'edge-left'">
      <template #meta><span class="doudizhu-player-panel__role">{{ roleLabel }}</span><DoudizhuPlayerTags :player-state="playerState" /></template>
    </TurnPlayerPanel>
    <div
      v-if="showRemainingHand"
      class="doudizhu-player-panel__terminal-hand"
      :class="`doudizhu-player-panel__terminal-hand--${layout}`"
      :aria-label="`${nickname} 剩余手牌`"
    >
      <template v-if="terminalHandCards.length">
        <DoudizhuCard
          v-for="(card, index) in terminalHandCards"
          :key="card.cardInstanceId"
          :card="card"
          class="doudizhu-player-panel__terminal-card"
          :style="{ zIndex: index + 1 }"
        />
      </template>
      <p v-else class="doudizhu-player-panel__terminal-empty">手牌已出完</p>
    </div>
    <div v-else-if="visibleCards.length" class="doudizhu-player-panel__visible-cards">
      <DoudizhuCard
        v-for="card in visibleCards"
        :key="card.cardInstanceId"
        :card="card"
        class="doudizhu-player-panel__mini-card"
      />
    </div>
    <div
      v-if="playedCardDisplays.length || actionFeedback"
      class="doudizhu-player-panel__operation-feedback"
      :class="`doudizhu-player-panel__operation-feedback--${layout}`"
      :aria-label="operationFeedbackAriaLabel"
    >
      <template v-if="playedCardDisplays.length">
        <span class="doudizhu-player-panel__played-cards">
          <DoudizhuCard
            v-for="(display, index) in playedCardDisplays"
            :key="display.card.cardInstanceId"
            :card="display.card"
            :assigned-rank-code="display.assignedRankCode"
            :style="{ zIndex: index + 1 }"
          />
        </span>
        <span v-if="playedComboLabel" class="doudizhu-player-panel__played-label">
          {{ playedComboLabel }}
        </span>
      </template>
      <span
        v-else
        class="doudizhu-player-panel__action-feedback"
        :class="`doudizhu-player-panel__action-feedback--${actionFeedbackTone}`"
      >
        {{ actionFeedback }}
      </span>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue';
import { TurnPlayerPanel } from '../../../components/game/index.js';
import botAvatarUrl from '../../../assets/games/doudizhu/doudizhu-bot-avatar.png';
import { formatDoudizhuRoleLabel } from '../doudizhuDisplayText.js';
import { normalizeHandCard, sortHandCards } from '../doudizhuGameViewUtils.js';
import DoudizhuCard from './DoudizhuCard.vue';
import DoudizhuPlayerTags from './DoudizhuPlayerTags.vue';

const props = defineProps({
  nickname: { type: String, default: '玩家' },
  playerState: { type: Object, default: () => ({}) },
  isCurrentTurn: { type: Boolean, default: false },
  isAi: { type: Boolean, default: false },
  managedLabel: { type: String, default: '' },
  managedBadgeClass: { type: String, default: '' },
  showCountdown: { type: Boolean, default: false },
  countdownSeconds: { type: Number, default: 30 },
  countdownExpiresAtMs: { type: Number, default: null },
  actionFeedback: { type: String, default: '' },
  actionFeedbackTone: { type: String, default: 'affirmative' },
  playedCardDisplays: { type: Array, default: () => [] },
  playedComboLabel: { type: String, default: '' },
  showRemainingHand: { type: Boolean, default: false },
  layout: { type: String, default: 'default' }
});

const handCount = computed(() => Number(props.playerState?.handCount) || 0);

const roleLabel = computed(() => {
  if (props.playerState?.isLandlord) {
    return formatDoudizhuRoleLabel('landlord');
  }
  const role = String(props.playerState?.role || '').trim();
  return role ? formatDoudizhuRoleLabel(role) : formatDoudizhuRoleLabel('farmer');
});

const visibleCards = computed(() => {
  const list = props.playerState?.visibleCards;
  if (!Array.isArray(list)) {
    return [];
  }
  return sortHandCards(
    list.map((item) => normalizeHandCard(item)).filter((item) => item.cardInstanceId)
  );
});
const terminalHandCards = computed(() => sortHandCards(visibleCards.value));
const operationFeedbackAriaLabel = computed(() => (
  props.playedCardDisplays.length ? `${props.nickname} 出牌` : `${props.nickname} ${props.actionFeedback}`
));

const panelClassList = computed(() => ({
  'doudizhu-player-panel--active': props.isCurrentTurn,
  [`doudizhu-player-panel--${props.layout}`]: Boolean(props.layout)
}));
</script>
