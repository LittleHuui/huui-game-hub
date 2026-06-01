<template>
  <div
    v-if="hasDisplay"
    class="uno-player-action"
    :class="rootClassList"
    :title="ariaLabel"
    role="img"
    :aria-label="ariaLabel"
  >
    <img
      v-if="isCardPlayed"
      class="uno-player-action__card"
      :src="cardImageUrl"
      :alt="cardAltText"
      draggable="false"
    />

    <div v-else-if="isDisabled" class="uno-player-action__ban" aria-hidden="true">
      <span class="uno-player-action__ban-ring" />
      <span class="uno-player-action__ban-bar" />
    </div>

    <span v-else-if="isDraw" class="uno-player-action__draw">{{ drawLabel }}</span>

    <span v-else-if="isRank" class="uno-player-action__rank-value">{{ rankValue }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { resolveUnoCardAssetUrl } from '../unoAssetConfig.js';
import { UNO_PLAYER_ACTION_TYPE } from '../unoPlayerActionViewModel.js';
import './unoPlayerActionDisplay.css';

const props = defineProps({
  viewModel: {
    type: Object,
    default: null
  }
});

const actionType = computed(() => String(props.viewModel?.type || '').trim());

const isCardPlayed = computed(() => actionType.value === UNO_PLAYER_ACTION_TYPE.CARD_PLAYED);
const isDisabled = computed(() => actionType.value === UNO_PLAYER_ACTION_TYPE.DISABLED);
const isDraw = computed(() => actionType.value === UNO_PLAYER_ACTION_TYPE.DRAW);
const isRank = computed(() => actionType.value === UNO_PLAYER_ACTION_TYPE.RANK);

const hasDisplay = computed(
  () => isCardPlayed.value || isDisabled.value || isDraw.value || isRank.value
);

const cardCode = computed(() => String(props.viewModel?.cardCode || '').trim());

const cardImageUrl = computed(() => {
  if (!isCardPlayed.value || !cardCode.value) {
    return '';
  }
  return resolveUnoCardAssetUrl(cardCode.value);
});

const cardAltText = computed(() => (cardCode.value ? `打出 ${cardCode.value}` : '出牌'));

const drawCount = computed(() => {
  const count = Number(props.viewModel?.count);
  return Number.isFinite(count) && count > 0 ? count : 0;
});

const drawLabel = computed(() => (drawCount.value > 0 ? `摸+${drawCount.value}` : ''));

const rankValue = computed(() => {
  const rank = Number(props.viewModel?.rank);
  return Number.isFinite(rank) && rank > 0 ? rank : 0;
});

const rankTierClass = computed(() => {
  if (!isRank.value) {
    return '';
  }
  const rank = rankValue.value;
  if (rank === 1) {
    return 'uno-player-action--rank-gold';
  }
  if (rank === 2) {
    return 'uno-player-action--rank-silver';
  }
  if (rank === 3) {
    return 'uno-player-action--rank-bronze';
  }
  return 'uno-player-action--rank-plain';
});

const rootClassList = computed(() => ({
  'uno-player-action--card': isCardPlayed.value,
  'uno-player-action--disabled': isDisabled.value,
  'uno-player-action--draw': isDraw.value,
  'uno-player-action--rank': isRank.value,
  [rankTierClass.value]: Boolean(rankTierClass.value)
}));

const ariaLabel = computed(() => {
  if (isCardPlayed.value) {
    return cardAltText.value;
  }
  if (isDisabled.value) {
    return '被禁用';
  }
  if (isDraw.value) {
    return drawLabel.value;
  }
  if (isRank.value) {
    return `第 ${rankValue.value} 名`;
  }
  return '';
});
</script>
