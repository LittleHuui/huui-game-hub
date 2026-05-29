<template>
  <section class="uno-discard-area">
    <h3 v-if="title" class="uno-discard-area__title">{{ title }}</h3>
    <div class="uno-discard-area__pile">
      <div
        v-for="(item, index) in stackedCards"
        :key="item.key"
        class="uno-discard-area__card"
        :style="cardOffsetStyle(index)"
      >
        <UnoCard :card-code="item.cardCode" />
      </div>
      <p v-if="!stackedCards.length" class="empty-text uno-discard-area__empty">暂无弃牌</p>
    </div>
    <p v-if="currentColorLabel" class="muted-small uno-discard-area__color">
      当前花色：{{ currentColorLabel }}
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import UnoCard from './UnoCard.vue';
import { UNO_COLOR_OPTIONS } from '../unoGameConstants.js';

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  /** @type {import('vue').PropType<object[]>} */
  discardPileRecentCards: {
    type: Array,
    default: () => []
  },
  currentColor: {
    type: String,
    default: ''
  }
});

/**
 * @param {string} color
 * @returns {string}
 */
function resolveColorLabel(color) {
  const normalized = String(color || '').trim().toLowerCase();
  const matched = UNO_COLOR_OPTIONS.find((item) => item.value === normalized);
  return matched ? matched.key : normalized.toUpperCase();
}

const stackedCards = computed(() => {
  const list = Array.isArray(props.discardPileRecentCards) ? props.discardPileRecentCards : [];
  return list.slice(-2).map((item, index) => ({
    key: `${String(item?.cardInstanceId || '').trim()}-${Number(item?.sequence) || index}`,
    cardCode: String(item?.cardCode || '').trim()
  }));
});

const currentColorLabel = computed(() => {
  const color = String(props.currentColor || '').trim();
  return color ? resolveColorLabel(color) : '';
});

/**
 * @param {number} index
 * @returns {object}
 */
function cardOffsetStyle(index) {
  const offset = index * 14;
  return {
    zIndex: String(index + 1),
    transform: `translate(${offset}px, ${-offset * 0.35}px) rotate(${index * 2 - 2}deg)`
  };
}
</script>
