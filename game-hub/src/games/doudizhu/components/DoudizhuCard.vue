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
    <svg v-else class="doudizhu-card__face" viewBox="0 0 72 104" preserveAspectRatio="xMidYMid meet" role="img" :aria-label="cardTitle">
      <text v-if="faceDown" class="doudizhu-card__back-mark" x="36" y="58" text-anchor="middle">牌</text>
      <template v-else>
        <template v-if="isJoker">
          <text class="doudizhu-card__joker-label" x="11" y="19" text-anchor="middle">
            <tspan v-for="(letter, index) in 'JOKER'" :key="index" x="11" :dy="index ? 13 : 0">{{ letter }}</tspan>
          </text>
          <image
            class="doudizhu-card__joker-clown"
            :href="jokerClownImage"
            x="24" y="29" width="39" height="46"
            preserveAspectRatio="xMidYMid meet"
            aria-hidden="true"
          />
        </template>
        <template v-else>
          <g v-for="position in ['top', 'bottom']" :key="position" class="doudizhu-card__index"
            :transform="position === 'bottom' ? 'rotate(180 36 52)' : undefined" aria-hidden="true">
            <text class="doudizhu-card__rank" x="6" y="23">{{ isLaizi ? laiziDisplayRank : displayRank }}</text>
            <path v-if="isLaizi" class="doudizhu-card__laizi-star" :d="starPath" transform="translate(7 28) scale(.5)" />
            <text v-else class="doudizhu-card__suit" x="12" y="47" text-anchor="middle">{{ suitSymbol }}</text>
            <text v-if="isSubstituted && position === 'top'" class="doudizhu-card__laizi-source-rank" x="12" y="53" text-anchor="middle">{{ originalRankCode }}</text>
          </g>
          <path v-if="isLaizi" class="doudizhu-card__laizi-star doudizhu-card__center" :d="starPath" transform="translate(26 39) scale(1.15)" aria-hidden="true" />
          <text v-else class="doudizhu-card__suit-center doudizhu-card__center" x="38" y="63" text-anchor="middle" aria-hidden="true">{{ suitSymbol }}</text>
        </template>
      </template>
    </svg>
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
// All face geometry uses the same 72 × 104 design coordinates, scaled by the SVG viewport.
const starPath = 'M12 2 15 8.5 22 9.5 17 14.5 18 22 12 18.5 6 22 7 14.5 2 9.5 9 8.5Z';

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

const displayRank = computed(() => displayLabel.value || props.card?.rankCode || '');

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
