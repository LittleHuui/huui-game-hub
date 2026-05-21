<template>
  <div class="game2048-hud">
    <template v-if="section === 'config'">
      <p class="game2048-hud__mode muted-small">经典模式 · 标准难度</p>
      <div class="game2048-hud__actions">
        <button
          type="button"
          class="side-action"
          :class="startButtonClass"
          :disabled="restartDisabled"
          @click="$emit('start-or-restart')"
        >
          {{ startButtonLabel }}
        </button>
        <button
          v-if="showEndGame"
          type="button"
          class="side-action btn-action-end"
          :disabled="!canEndGame"
          @click="$emit('end')"
        >
          结束对局
        </button>
      </div>
    </template>
    <template v-else>
      <GameHudStats :theme-seed="themeSeed">
        <GameStatGrid compact :columns="3" min-column-width="84px">
          <GameStatCard :label="t.score" :value="score" tone="accent" icon="★" layout="inline" />
          <GameStatCard :label="t.maxTile" :value="maxTile" icon="▣" layout="inline" />
          <GameStatCard :label="t.moves" :value="moves" icon="↔" layout="inline" />
          <GameStatCard
            :label="t.duration"
            :value="`${elapsedSec}s`"
            helper="累计"
            icon="⏱"
            layout="inline"
          />
          <GameStatCard :label="t.clearUses" :value="clearCellUses" icon="🔨" layout="inline" />
          <GameStatCard :label="t.penalty" :value="scorePenalty" tone="muted" layout="inline" />
          <GameStatCard
            :label="t.reward"
            :value="rewardScore"
            helper="预计"
            icon="◎"
            layout="inline"
          />
        </GameStatGrid>
        <GameStatQuotaBar :items="propQuotas" />
        <p v-if="reached2048" class="game2048-hud__badge">已达成 2048</p>
        <p v-if="message" class="game-hud-stats__message">{{ message }}</p>
      </GameHudStats>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import GameHudStats from '../../../components/game/GameHudStats.vue';
import GameStatCard from '../../../components/game/GameStatCard.vue';
import GameStatGrid from '../../../components/game/GameStatGrid.vue';
import GameStatQuotaBar from '../../../components/game/GameStatQuotaBar.vue';

const t = {
  score: '得分',
  maxTile: '最大块',
  moves: '步数',
  duration: '用时',
  clearUses: '清除锤',
  penalty: '扣分',
  reward: '平台积分'
};

const props = defineProps({
  section: {
    type: String,
    default: 'hud'
  },
  gameStatus: {
    type: String,
    default: 'idle',
    validator: (v) => ['idle', 'playing', 'paused', 'settling', 'ended'].includes(v)
  },
  showEndGame: { type: Boolean, default: false },
  canEndGame: { type: Boolean, default: false },
  score: { type: Number, default: 0 },
  moves: { type: Number, default: 0 },
  maxTile: { type: Number, default: 0 },
  elapsedSec: { type: Number, default: 0 },
  clearCellUses: { type: Number, default: 0 },
  scorePenalty: { type: Number, default: 0 },
  rewardScore: { type: Number, default: 0 },
  reached2048: { type: Boolean, default: false },
  message: { type: String, default: '' },
  propQuotas: { type: Array, default: () => [] },
  restartDisabled: { type: Boolean, default: false },
  themeSeed: { type: [Number, String], default: 'random' }
});

defineEmits(['start-or-restart', 'end']);

const startButtonLabel = computed(() => {
  if (
    props.gameStatus === 'playing' ||
    props.gameStatus === 'paused' ||
    props.gameStatus === 'settling' ||
    props.gameStatus === 'ended'
  ) {
    return '重新开始';
  }
  return '开始游戏';
});

const startButtonClass = computed(() =>
  props.gameStatus === 'idle' ? 'btn-action-start' : 'btn-action-restart'
);
</script>

<style scoped>
.game2048-hud__mode {
  margin: 0 0 10px;
}

.game2048-hud__actions {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.game2048-hud__actions .side-action:first-child {
  margin-top: 0;
}

.game2048-hud__badge {
  margin: 8px 0 0;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: #fef3c7;
  background: linear-gradient(90deg, rgba(251, 191, 36, 0.35), rgba(236, 72, 153, 0.35));
  display: inline-block;
}
</style>
