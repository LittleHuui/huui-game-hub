<template>
  <section class="doudizhu-table" aria-live="polite">
    <div
      v-if="lastPlayCardDisplays.length"
      class="doudizhu-table__last-play"
      :class="`doudizhu-table__last-play--${lastPlayPosition}`"
      :aria-label="lastPlayLabel"
    >
      <div class="doudizhu-table__card-row">
        <DoudizhuCard
          v-for="(display, index) in lastPlayCardDisplays"
          :key="display.card.cardInstanceId"
          :card="display.card"
          :assigned-rank-code="display.assignedRankCode"
          :style="{ zIndex: index + 1 }"
        />
      </div>
      <p v-if="lastPlayComboLabel" class="doudizhu-table__combo-label muted-small">
        {{ lastPlayComboLabel }}
      </p>
    </div>
    <p
      v-if="showPassHint"
      class="doudizhu-table__pass-hint"
      :class="`doudizhu-table__pass-hint--${lastPassPosition}`"
      :aria-label="lastPassLabel"
    >
      不出
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import { formatDoudizhuComboLabel } from '../doudizhuDisplayText.js';
import {
  buildPlayedCardDisplays,
  normalizeLastPlay
} from '../doudizhuGameViewUtils.js';
import DoudizhuCard from './DoudizhuCard.vue';

const props = defineProps({
  gameState: { type: Object, default: () => ({}) },
  lastPlayPlayerNickname: { type: String, default: '' },
  passPlayerIds: { type: Array, default: () => [] },
  lastPlayPosition: { type: String, default: 'center' },
  lastPassPlayerNickname: { type: String, default: '' },
  lastPassPosition: { type: String, default: 'center' }
});

const lastPlayInfo = computed(() => normalizeLastPlay(props.gameState?.lastPlay));

const lastPlayCardDisplays = computed(() => buildPlayedCardDisplays(
  props.gameState?.lastPlayCards,
  props.gameState?.lastPlay
));

const lastPlayComboLabel = computed(() => {
  const comboType = lastPlayInfo.value?.comboType;
  return comboType ? formatDoudizhuComboLabel(comboType) : '';
});

const showPassHint = computed(() => {
  const passes = Array.isArray(props.passPlayerIds) ? props.passPlayerIds : [];
  return passes.length > 0;
});

const lastPlayLabel = computed(() => {
  const nickname = String(props.lastPlayPlayerNickname || '').trim();
  if (nickname && lastPlayCardDisplays.value.length) {
    return `${nickname} 出牌`;
  }
  if (nickname && showPassHint.value) {
    return `${nickname} 不出`;
  }
  return '上一手';
});

const lastPassLabel = computed(() => {
  const nickname = String(props.lastPassPlayerNickname || '').trim();
  return nickname ? `${nickname} 不出` : '不出';
});

</script>
