<template>
  <figure class="uno-card" :title="displayCode">
    <img
      v-if="imageUrl"
      class="uno-card__face"
      :class="{ 'uno-card__face--back': faceDown }"
      :src="imageUrl"
      :alt="altText"
      draggable="false"
    />
    <div v-else class="uno-card__face uno-card__face--empty" />
    <figcaption v-if="showCode" class="uno-card__code">{{ displayCode }}</figcaption>
  </figure>
</template>

<script setup>
import { computed } from 'vue';
import { resolveUnoCardAssetUrl, UNO_ASSET_CONFIG } from '../unoAssetConfig.js';
import './unoCard.css';

const props = defineProps({
  cardCode: {
    type: String,
    default: ''
  },
  faceDown: {
    type: Boolean,
    default: false
  },
  showCode: {
    type: Boolean,
    default: false
  }
});

const displayCode = computed(() => {
  if (props.faceDown) {
    return 'card_back';
  }
  return String(props.cardCode || '').trim();
});

const imageUrl = computed(() => {
  if (props.faceDown) {
    return UNO_ASSET_CONFIG.cardBack || resolveUnoCardAssetUrl('games/uno/cards/card_back.png');
  }
  const key = displayCode.value;
  if (!key) {
    return '';
  }
  return resolveUnoCardAssetUrl(key);
});

const altText = computed(() => {
  if (props.faceDown) {
    return 'UNO 牌背';
  }
  return displayCode.value ? `UNO ${displayCode.value}` : 'UNO 牌';
});
</script>
