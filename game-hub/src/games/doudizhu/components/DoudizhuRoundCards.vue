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
    <p class="doudizhu-round-cards__caption" data-test="global-multiplier">
      当前倍率 ×{{ globalMultiplier }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { normalizeHandCard } from '../doudizhuGameViewUtils.js';
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

<style scoped>
.doudizhu-round-cards {
  position: relative;
  grid-column: 2;
  justify-self: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: max-content;
  margin-inline: auto;
}

.doudizhu-round-cards__bottom {
  display: flex;
  justify-content: center;
  gap: 4px;
}

.doudizhu-round-cards :deep(.doudizhu-card) {
  --doudizhu-laizi-rank-size: 10px;
  --doudizhu-laizi-corner-star-size: 7px;
  --doudizhu-laizi-center-star-size: 17px;
  --doudizhu-laizi-source-rank-size: 8px;
  --doudizhu-laizi-index-inset: 3px;
  width: 42px;
  height: 59px;
}

.doudizhu-round-cards__bottom :deep(.doudizhu-card__joker-label) {
  top: 0.16rem;
  left: 0.13rem;
  font-size: 0.33rem;
  line-height: 0.8;
}

.doudizhu-round-cards__bottom :deep(.doudizhu-card__joker-clown) {
  width: 42%;
  max-height: 42%;
}

.doudizhu-round-cards__laizi {
  position: absolute;
  top: 0;
  right: calc(100% + 16px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.doudizhu-round-cards__caption {
  margin: 0;
  color: rgba(226, 232, 240, 0.78);
  font-size: 0.66rem;
  line-height: 1;
  white-space: nowrap;
}
</style>
