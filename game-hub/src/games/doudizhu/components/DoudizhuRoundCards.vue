<template>
  <div class="doudizhu-round-cards">
    <div
      v-if="laiziRankCode"
      class="doudizhu-round-cards__laizi"
      :aria-label="`癞子点数 ${laiziRankCode}`"
      data-test="laizi-indicator"
    >
      <DoudizhuCard :card="laiziIndicator" />
      <span class="doudizhu-round-cards__caption">本局癞子</span>
    </div>
    <div class="doudizhu-round-cards__bottom" aria-label="底牌">
      <DoudizhuCard
        v-for="card in bottomCardSlots"
        :key="card.cardInstanceId"
        :card="card"
        :face-down="!revealedBottomCards.length"
      />
    </div>
    <p class="doudizhu-round-cards__caption doudizhu-round-cards__scoring">
      <span data-test="base-score">底分 {{ baseScore }}</span>
      <span data-test="global-multiplier">倍率 ×{{ globalMultiplier }}</span>
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { normalizeHandCard } from '../doudizhuGameViewUtils.js';
import { formatDoudizhuBaseScore } from '../doudizhuDisplayText.js';
import DoudizhuCard from './DoudizhuCard.vue';

const props = defineProps({
  gameState: { type: Object, default: () => ({}) }
});

// 癞子指示仅展示公开点数，不代表底牌或任意玩家持有的牌实体。
const laiziRankCode = computed(() => props.gameState?.enableLaizi
  ? String(props.gameState?.laiziRankCode || '').trim()
  : ''
);
const laiziIndicator = computed(() => ({ rankCode: laiziRankCode.value, isLaizi: true }));
const baseScore = computed(() => formatDoudizhuBaseScore(props.gameState?.baseScore));
const globalMultiplier = computed(() => Math.max(1, Number(props.gameState?.globalMultiplier) || 1));
const revealedBottomCards = computed(() => {
  if (!props.gameState?.bottomCardsRevealed) return [];
  const cards = props.gameState?.bottomCards;
  return Array.isArray(cards)
    ? cards.map(normalizeHandCard).filter((card) => card.cardInstanceId)
    : [];
});
const bottomCardSlots = computed(() => revealedBottomCards.value.length
  ? revealedBottomCards.value
  : [1, 2, 3].map((index) => ({ cardInstanceId: `bottom-card-${index}` }))
);
</script>
