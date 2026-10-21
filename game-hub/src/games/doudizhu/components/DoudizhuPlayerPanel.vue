<template>
  <article
    class="doudizhu-player-panel"
    :class="panelClassList"
  >
    <div class="doudizhu-player-panel__identity">
      <div class="doudizhu-player-panel__portrait">
        <div class="doudizhu-player-panel__avatar" aria-hidden="true">
          <img v-if="isAi" :src="botAvatarUrl" alt="" />
          <span v-else>{{ avatarInitial }}</span>
        </div>
        <div class="doudizhu-player-panel__countdown-slot">
          <TurnCountdown
            v-if="showCountdown"
            :seconds="countdownSeconds"
            :expires-at-ms="countdownExpiresAtMs"
            compact
          />
        </div>
      </div>
      <div class="doudizhu-player-panel__main">
        <div class="doudizhu-player-panel__heading">
          <h3
            class="doudizhu-player-panel__name-anchor"
            @mouseenter="showNameTooltip"
            @mouseleave="hideNameTooltip"
          >
            <span
              class="doudizhu-player-panel__name"
              tabindex="0"
              :aria-describedby="nameTooltipVisible ? nameTooltipId : undefined"
              @focus="showNameTooltip"
              @blur="hideNameTooltip"
              @keydown.esc="hideNameTooltip"
            >{{ nickname }}</span>
            <span
              v-if="nameTooltipVisible"
              :id="nameTooltipId"
              class="doudizhu-player-panel__name-tooltip"
              role="tooltip"
            >{{ nickname }}</span>
          </h3>
          <span v-if="roleLabel" class="doudizhu-player-panel__role">
            <span
              class="doudizhu-player-panel__icon"
              :class="isLandlord ? 'doudizhu-player-panel__icon--landlord' : 'doudizhu-player-panel__icon--farmer'"
              aria-hidden="true"
            />
            {{ roleLabel }}
          </span>
        </div>
        <div class="doudizhu-player-panel__status">
          <DoudizhuPlayerTags class="doudizhu-player-panel__status-row" :player-state="playerState" />
          <p class="doudizhu-player-panel__status-row">
            <span v-if="managedLabel" :class="managedBadgeClass">{{ managedLabel }}</span>
            <span v-if="isAi">AI</span>
          </p>
        </div>
        <p class="doudizhu-player-panel__meta" :aria-label="`手牌 ${handCount} 张`">
          <span
            class="doudizhu-player-panel__icon doudizhu-player-panel__icon--cards"
            aria-hidden="true"
          />
          <span>{{ handCount }}</span>
        </p>
      </div>
    </div>
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
import { computed, ref, useId } from 'vue';
import { TurnCountdown } from '../../../components/game/index.js';
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

const avatarInitial = computed(() => {
  const name = String(props.nickname || '').trim();
  return name ? name.charAt(0) : '?';
});

const handCount = computed(() => Number(props.playerState?.handCount) || 0);
const nameTooltipId = useId();
const nameTooltipVisible = ref(false);

/** 显示完整昵称，不改变姓名栏的布局宽度。 */
function showNameTooltip() {
  nameTooltipVisible.value = true;
}

/** 隐藏昵称提示，支持失焦、离开及 Escape。 */
function hideNameTooltip() {
  nameTooltipVisible.value = false;
}

const isLandlord = computed(() => (
  Boolean(props.playerState?.isLandlord) || props.playerState?.role === 'landlord'
));

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

<style scoped src="./doudizhuPlayerPanel.css"></style>
