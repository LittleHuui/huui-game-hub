<template>
  <AppModal :visible="visible" title="对局结算" @close="$emit('close')">
    <div class="gomoku-settlement">
      <p v-if="winnerNickname" class="gomoku-settlement__winner">
        胜利者：<strong>{{ winnerNickname }}</strong>
        <span class="muted-small">（{{ stoneLabel }}）</span>
      </p>
      <p v-else class="muted-small gomoku-settlement__winner">对局已结束</p>
      <p class="gomoku-settlement__meta muted-small">胜利原因：{{ finishReasonLabel }}</p>
      <p class="gomoku-settlement__meta muted-small">总手数：{{ movesCount }}</p>
    </div>
    <template #footer>
      <div class="room-hub-form__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--primary game-action-btn--md"
          @click="$emit('close')"
        >
          返回房间
        </button>
        <button
          type="button"
          class="game-action-btn game-action-btn--ghost game-action-btn--md"
          @click="$emit('lobby')"
        >
          返回大厅
        </button>
      </div>
    </template>
  </AppModal>
</template>

<script setup>
import { computed } from 'vue';
import AppModal from '../../../components/AppModal.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  winnerPlayerId: { type: String, default: '' },
  winnerStone: { type: String, default: '' },
  finishReason: { type: String, default: '' },
  movesCount: { type: Number, default: 0 },
  members: { type: Array, default: () => [] }
});

defineEmits(['close', 'lobby']);

const winnerNickname = computed(() => {
  const playerId = String(props.winnerPlayerId || '').trim();
  if (!playerId) {
    return '';
  }
  const members = Array.isArray(props.members) ? props.members : [];
  const matched = members.find((item) => String(item?.playerId || '').trim() === playerId);
  return String(matched?.nickname || '').trim() || playerId;
});

const stoneLabel = computed(() => {
  const stone = String(props.winnerStone || '').toUpperCase();
  if (stone === 'WHITE') {
    return '白棋';
  }
  if (stone === 'BLACK') {
    return '黑棋';
  }
  return '—';
});

const finishReasonLabel = computed(() => {
  const reason = String(props.finishReason || '').trim();
  if (reason === 'FIVE_IN_ROW') {
    return '五子连珠';
  }
  if (reason === 'RESIGN') {
    return '对手认输';
  }
  return reason || '对局结束';
});
</script>
