<template>
  <AppModal :visible="visible" title="对局结算" @close="$emit('close')">
    <div class="uno-settlement">
      <p v-if="winnerLabel" class="uno-settlement__winner">
        胜利者：<strong>{{ winnerLabel }}</strong>
      </p>
      <p v-else class="muted-small uno-settlement__winner">对局已结束</p>

      <ol v-if="rankRows.length" class="uno-settlement__list">
        <li v-for="row in rankRows" :key="row.playerId" class="uno-settlement__item">
          <span class="uno-settlement__rank">{{ row.rankLabel }}</span>
          <span class="uno-settlement__name">{{ row.nickname }}</span>
          <span class="uno-settlement__meta muted-small">{{ row.handLabel }}</span>
        </li>
      </ol>
      <p v-else class="muted-small">暂无完整排名信息</p>

      <div class="room-hub-form__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--primary game-action-btn--md"
          @click="$emit('close')"
        >
          返回房间
        </button>
      </div>
    </div>
  </AppModal>
</template>

<script setup>
import { computed } from 'vue';
import AppModal from '../../../components/AppModal.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  rankings: { type: Array, default: () => [] },
  players: { type: Array, default: () => [] },
  members: { type: Array, default: () => [] }
});

defineEmits(['close']);

/**
 * @param {string} playerId
 * @returns {string}
 */
function resolveNickname(playerId) {
  const members = Array.isArray(props.members) ? props.members : [];
  const matched = members.find((item) => String(item?.playerId || '').trim() === playerId);
  const nickname = String(matched?.nickname || '').trim();
  return nickname || playerId;
}

const rankRows = computed(() => {
  const rankings = Array.isArray(props.rankings) ? [...props.rankings] : [];
  rankings.sort((left, right) => Number(left?.rank) - Number(right?.rank));
  const playerMap = new Map();
  const players = Array.isArray(props.players) ? props.players : [];
  for (const item of players) {
    const playerId = String(item?.playerId || '').trim();
    if (!playerId) {
      continue;
    }
    playerMap.set(playerId, item);
  }
  return rankings
    .map((item) => {
      const playerId = String(item?.playerId || '').trim();
      if (!playerId) {
        return null;
      }
      const rank = Number(item?.rank);
      const playerState = playerMap.get(playerId);
      const handCount = Number(playerState?.handCount);
      return {
        playerId,
        rankLabel: Number.isFinite(rank) && rank > 0 ? `第 ${rank} 名` : '—',
        nickname: resolveNickname(playerId),
        handLabel: Number.isFinite(handCount) ? `剩余 ${handCount} 张` : ''
      };
    })
    .filter(Boolean);
});

const winnerLabel = computed(() => {
  const first = rankRows.value[0];
  return first?.nickname || '';
});
</script>
