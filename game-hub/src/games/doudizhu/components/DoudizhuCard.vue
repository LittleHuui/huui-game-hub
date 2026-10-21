<template>
  <figure
    class="doudizhu-card"
    :class="cardClassList"
    :title="cardTitle"
  >
    <img
      v-if="imageUrl && !faceDown"
      class="doudizhu-card__image"
      :src="imageUrl"
      :alt="cardTitle"
      draggable="false"
      @error="onImageError"
    />
    <div v-else class="doudizhu-card__face">
      <span v-if="faceDown" class="doudizhu-card__back-mark">牌</span>
      <template v-else>
        <template v-if="isJoker">
          <span class="doudizhu-card__corner doudizhu-card__corner--top doudizhu-card__joker-label">
            JOKER
          </span>
          <img
            class="doudizhu-card__joker-clown"
            :src="jokerClownImage"
            alt=""
            aria-hidden="true"
            draggable="false"
          />
        </template>
        <template v-else-if="isLaizi">
          <span class="doudizhu-card__laizi-index doudizhu-card__laizi-index--top" aria-hidden="true">
            <span>{{ laiziDisplayRank }}</span>
            <span class="doudizhu-card__laizi-star" />
            <span v-if="isSubstituted" class="doudizhu-card__laizi-source-rank">{{ originalRankCode }}</span>
          </span>
          <span class="doudizhu-card__laizi-star doudizhu-card__laizi-star--center" aria-hidden="true" />
          <span class="doudizhu-card__laizi-index doudizhu-card__laizi-index--bottom" aria-hidden="true">
            <span>{{ laiziDisplayRank }}</span>
            <span class="doudizhu-card__laizi-star" />
          </span>
        </template>
        <template v-else>
          <span class="doudizhu-card__corner doudizhu-card__corner--top">
            {{ cornerTop }}
          </span>
          <span class="doudizhu-card__suit-center" aria-hidden="true">{{ suitSymbol }}</span>
          <span class="doudizhu-card__corner doudizhu-card__corner--bottom">
            {{ cornerBottom }}
          </span>
        </template>
      </template>
    </div>
  </figure>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import jokerClownImage from '../../../assets/games/doudizhu/joker-clown.png';
import { resolveDoudizhuCardImageUrl } from '../doudizhuCardAssets.js';

const props = defineProps({
  card: {
    type: Object,
    default: () => ({})
  },
  faceDown: {
    type: Boolean,
    default: false
  },
  selected: {
    type: Boolean,
    default: false
  },
  assignedRankCode: {
    type: String,
    default: ''
  }
});

const imageBroken = ref(false);

watch(
  () => `${String(props.card?.cardInstanceId || '').trim()}\u0000${String(props.card?.image || '').trim()}`,
  () => {
    imageBroken.value = false;
  }
);

const displayLabel = computed(() => String(props.card?.displayLabel || '').trim());
const jokerKind = computed(() => resolveJokerKind(props.card));
const isJoker = computed(() => jokerKind.value !== '');
const isBigJoker = computed(() => jokerKind.value === 'big');
const isLaizi = computed(() => Boolean(props.card?.isLaizi) && !isJoker.value);
const originalRankCode = computed(() => String(props.card?.rankCode || displayLabel.value).trim().toUpperCase());
const laiziDisplayRank = computed(() => {
  const assignedRank = String(props.assignedRankCode || '').trim().toUpperCase();
  return isLaizi.value && /^(?:[2-9]|10|J|Q|K|A)$/.test(assignedRank)
    ? assignedRank
    : originalRankCode.value;
});
const isSubstituted = computed(() => isLaizi.value && laiziDisplayRank.value !== originalRankCode.value);
const displayColor = computed(() => String(props.card?.displayColor || '').trim().toUpperCase());
const cardTitle = computed(() => {
  if (props.faceDown) {
    return '牌背';
  }
  if (isLaizi.value) {
    return isSubstituted.value
      ? `${originalRankCode.value}（癞子，当 ${laiziDisplayRank.value} 使用）`
      : `${originalRankCode.value}（癞子）`;
  }
  if (displayLabel.value) {
    return displayLabel.value;
  }
  if (isJoker.value) {
    return isBigJoker.value ? '大王' : '小王';
  }
  return String(props.card?.cardCode || '').trim() || '扑克牌';
});

const suitSymbol = computed(() => {
  const suit = String(props.card?.suitCode || '').trim().toUpperCase();
  if (suit === 'SPADE') {
    return '♠';
  }
  if (suit === 'HEART') {
    return '♥';
  }
  if (suit === 'CLUB') {
    return '♣';
  }
  if (suit === 'DIAMOND') {
    return '♦';
  }
  return '';
});

const cornerTop = computed(() => {
  const label = displayLabel.value || props.card?.rankCode || '';
  return suitSymbol.value ? `${label}${suitSymbol.value}` : label;
});

const cornerBottom = computed(() => cornerTop.value);

const imageUrl = computed(() => {
  if (props.faceDown || isJoker.value || isLaizi.value || imageBroken.value) {
    return '';
  }
  return resolveDoudizhuCardImageUrl(props.card?.image);
});

const cardClassList = computed(() => ({
  'doudizhu-card--selected': props.selected,
  'doudizhu-card--face-down': props.faceDown,
  'doudizhu-card--red': !props.faceDown && (isBigJoker.value || (!isJoker.value && displayColor.value === 'RED')),
  'doudizhu-card--black': !props.faceDown && !isBigJoker.value && (isJoker.value || displayColor.value === 'BLACK' || !displayColor.value),
  'doudizhu-card--joker': !props.faceDown && isJoker.value,
  'doudizhu-card--joker-big': !props.faceDown && isBigJoker.value,
  'doudizhu-card--joker-small': !props.faceDown && isJoker.value && !isBigJoker.value,
  'doudizhu-card--laizi': !props.faceDown && isLaizi.value,
  'doudizhu-card--substituted': !props.faceDown && isSubstituted.value
}));

/**
 * 从斗地主牌的类型、点数和标识判断大小王，仅用于牌面视觉。
 * @param {object|null|undefined} card
 * @returns {'big'|'small'|''}
 */
function resolveJokerKind(card) {
  const source = card || {};
  const category = String(source.category || '').trim().toUpperCase();
  const rankCode = String(source.rankCode || '').trim().toUpperCase();
  const cardCode = String(source.cardCode || '').trim().toUpperCase();
  const label = String(source.displayLabel || '').trim();
  const rankValue = Number(source.rankValue);
  const identifier = `${rankCode} ${cardCode} ${label}`;
  const isJokerCard = Boolean(source.isJoker) || category === 'JOKER' || /JOKER|[大小]王/.test(identifier);
  if (!isJokerCard) {
    return '';
  }
  if (rankValue >= 17 || /BIG|大王/.test(identifier)) {
    return 'big';
  }
  return 'small';
}

/**
 * 图片加载失败时回退 CSS 牌面。
 */
function onImageError() {
  imageBroken.value = true;
}
</script>
