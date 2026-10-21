<template>
  <AppModal
    class="doudizhu-settlement-modal"
    :visible="visible"
    :title="winnerBanner?.title || '斗地主结算'"
    :closable="canDismiss"
    :mask-closable="canDismiss"
    @close="emitClose"
  >
    <div class="doudizhu-settlement" data-test="settlement-dialog">
      <div v-if="winnerBanner" class="doudizhu-settlement__banner">
        <img :src="winnerBanner.src" :alt="winnerBanner.title" />
      </div>
      <p v-else-if="winnerLabel" class="doudizhu-settlement__winner">
        <strong>{{ winnerLabel }}</strong>
      </p>

      <p class="doudizhu-settlement__multiplier">
        <span data-test="settlement-base-score">底分 {{ baseScore }}</span>
        <span data-test="settlement-multiplier">倍率 ×{{ globalMultiplier }}</span>
      </p>

      <ul v-if="isCompleted && playerRows.length" class="doudizhu-settlement__list">
        <li
          v-for="row in playerRows"
          :key="row.playerId"
          class="doudizhu-settlement__item"
          :class="{ 'doudizhu-settlement__item--viewer': row.playerId === viewerPlayerId }"
          :data-test="`settlement-player-${row.playerId}`"
        >
          <div
            class="doudizhu-settlement__avatar"
            :class="{ 'doudizhu-settlement__avatar--bot': row.isAi }"
            aria-hidden="true"
          >
            <img v-if="row.avatarUrl" :src="row.avatarUrl" alt="" />
            <span v-else>{{ row.nickname.charAt(0) || '?' }}</span>
          </div>
          <div class="doudizhu-settlement__identity">
            <span class="doudizhu-settlement__name" :title="row.nickname">{{ row.nickname }}</span>
            <span class="doudizhu-settlement__role">
              <span
                class="doudizhu-settlement__role-icon"
                :class="`doudizhu-settlement__role-icon--${row.role.toLowerCase()}`"
                aria-hidden="true"
              />
              {{ formatDoudizhuRoleLabel(row.role) }}
            </span>
          </div>
          <div :class="scoreDeltaClass(row.actualDelta)" data-test="actual-delta">
            <span class="doudizhu-settlement__score-label">积分</span>
            <span>{{ formatScore(row.actualDelta) }}</span>
          </div>
        </li>
      </ul>
      <p v-else class="doudizhu-settlement__waiting" data-test="settlement-waiting">
        {{ isFailed ? '积分结算未完成' : '积分结算中…' }}
      </p>
    </div>
    <template #footer>
      <div class="doudizhu-settlement__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--primary game-action-btn--md"
          :disabled="!canDismiss"
          data-test="return-room"
          @click="emitClose"
        >
          {{ isPending ? '平台积分结算中' : '返回房间' }}
        </button>
      </div>
    </template>
  </AppModal>
</template>

<script setup>
import { computed } from 'vue';
import AppModal from '../../../components/AppModal.vue';
import botAvatar from '../../../assets/games/doudizhu/doudizhu-bot-avatar.png';
import farmerVictoryBanner from '../../../assets/games/doudizhu/settlement-farmer-victory.png';
import landlordVictoryBanner from '../../../assets/games/doudizhu/settlement-landlord-victory.png';
import {
  formatDoudizhuBaseScore,
  formatDoudizhuRoleLabel,
  formatDoudizhuWinnerRoleLabel
} from '../doudizhuDisplayText.js';
import { mergeDoudizhuSettlementRows } from '../doudizhuSettlementMerge.js';

const props = defineProps({
  visible: { type: Boolean, default: false },
  settlement: { type: Object, default: () => ({}) },
  terminalMetadata: { type: Object, default: null },
  members: { type: Array, default: () => [] },
  viewerPlayerId: { type: String, default: '' },
  canDismiss: { type: Boolean, default: false }
});
const emit = defineEmits(['close']);
const WINNER_BANNERS = Object.freeze({
  farmer: { src: farmerVictoryBanner, title: '农民胜利' },
  landlord: { src: landlordVictoryBanner, title: '地主胜利' }
});
const membersByPlayer = computed(() => new Map(
  props.members.map((member) => [String(member?.playerId || '').trim(), member])
));

/**
 * 仅在终局控制器允许时发送关闭事件。
 * @returns {void}
 */
function emitClose() {
  if (props.canDismiss) emit('close');
}

/**
 * 解析玩家昵称。
 * @param {string} playerId
 * @returns {string}
 */
function resolveNickname(playerId) {
  const matched = membersByPlayer.value.get(playerId);
  return String(matched?.nickname || '').trim() || playerId;
}

/**
 * 格式化积分变化。
 * @param {number|null|undefined} value
 * @returns {string}
 */
function formatScore(value) {
  if (value == null || value === '') return '0';
  const number = Number(value);
  if (!Number.isFinite(number)) return '0';
  return number > 0 ? `+${number}` : String(number);
}

/**
 * 解析积分变化的颜色类名。
 * @param {number|null|undefined} value
 * @returns {string}
 */
function scoreDeltaClass(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number === 0) return 'doudizhu-settlement__score';
  return number > 0
    ? 'doudizhu-settlement__score doudizhu-settlement__score--positive'
    : 'doudizhu-settlement__score doudizhu-settlement__score--negative';
}

const winnerLabel = computed(() => {
  const role = String(props.settlement?.winnerRole || '').trim();
  return role ? formatDoudizhuWinnerRoleLabel(role) : '';
});
const winnerBanner = computed(() =>
  WINNER_BANNERS[String(props.settlement?.winnerRole || '').trim().toLowerCase()] || null
);
const globalMultiplier = computed(() =>
  Math.max(1, Number(props.settlement?.globalMultiplier) || 1)
);
const baseScore = computed(() => formatDoudizhuBaseScore(props.settlement?.baseScore));
const settlementStatus = computed(() =>
  String(props.terminalMetadata?.settlementStatus || '').trim()
);
const isPending = computed(() => settlementStatus.value === 'PENDING');
const isCompleted = computed(() => settlementStatus.value === 'COMPLETED');
const isFailed = computed(() => settlementStatus.value === 'FAILED');
const playerRows = computed(() =>
  mergeDoudizhuSettlementRows({
    theoreticalSettlements: props.settlement?.playerSettlements,
    platformSettlements: props.terminalMetadata?.settlementResult?.playerSettlements,
    resolveNickname
  }).map((row) => {
    const member = membersByPlayer.value.get(row.playerId);
    const isAi = Boolean(member?.isAi);
    return {
      ...row,
      isAi,
      avatarUrl: isAi ? botAvatar : String(member?.avatar || '').trim()
    };
  })
);
</script>

<style scoped src="./doudizhuSettlementDialog.css"></style>
