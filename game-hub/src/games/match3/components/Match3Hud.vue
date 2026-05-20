<template>
  <div class="match3-hud" :class="`match3-hud--${section}`">
    <template v-if="section === 'config' || section === 'all'">
      <div class="muted-small">{{ t.modeSection }}</div>
      <div class="game-mode-tabs">
        <button
          type="button"
          class="game-mode-tab"
          :class="{ 'game-mode-tab--active': mode === 'timed' }"
          :disabled="locked"
          @click="$emit('change-mode', 'timed')"
        >
          {{ t.timed }}
        </button>
        <button
          type="button"
          class="game-mode-tab"
          :class="{ 'game-mode-tab--active': mode === 'endless' }"
          :disabled="locked"
          @click="$emit('change-mode', 'endless')"
        >
          {{ t.endless }}
        </button>
      </div>
      <div class="match3-actions">
        <button
          type="button"
          class="side-action btn-action-restart"
          :disabled="restartDisabled"
          @click="$emit('restart')"
        >
          {{ t.restart }}
        </button>
        <button
          type="button"
          class="side-action btn-action-end"
          :disabled="!canEndGame"
          @click="$emit('end')"
        >
          {{ t.endGame }}
        </button>
      </div>
    </template>

    <template v-if="section === 'hud' || section === 'all'">
      <GameHudStats :theme-seed="themeSeed">
        <GameStatGrid compact :columns="3" min-column-width="84px">
          <GameStatCard :label="t.score" :value="score" tone="accent" icon="★" layout="inline" />
          <GameStatCard
            :label="timeLabel"
            :value="timeValue"
            :helper="timeHelper"
            icon="⏱"
            layout="inline"
          />
          <GameStatCard :label="t.moves" :value="moves" icon="↔" layout="inline" />
          <GameStatCard :label="t.comboMax" :value="comboMax" icon="⚡" layout="inline" />
          <GameStatCard :label="t.mode" :value="modeShortLabel" tone="muted" layout="inline" />
        </GameStatGrid>
        <GameStatQuotaBar :items="propQuotas" />
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
  modeSection: '模式 · 操作',
  timed: '限时',
  endless: '无限',
  restart: '重新开始',
  endGame: '结束对局',
  score: '得分',
  moves: '步数',
  comboMax: '连击',
  remaining: '剩余',
  elapsed: '用时',
  mode: '模式'
};

const props = defineProps({
  section: {
    type: String,
    default: 'all',
    validator: (v) => ['config', 'hud', 'all'].includes(v)
  },
  mode: { type: String, required: true },
  score: { type: Number, required: true },
  moves: { type: Number, required: true },
  comboMax: { type: Number, required: true },
  remainingSec: { type: Number, required: true },
  elapsedSec: { type: Number, required: true },
  gameStatus: {
    type: String,
    required: true,
    validator: (v) => ['idle', 'playing', 'paused', 'ended'].includes(v)
  },
  locked: { type: Boolean, required: true },
  restartDisabled: { type: Boolean, default: false },
  message: { type: String, required: true },
  propQuotas: { type: Array, default: () => [] },
  themeSeed: { type: [Number, String], default: 'random' }
});

defineEmits(['change-mode', 'restart', 'end']);

const canEndGame = computed(
  () => props.gameStatus === 'playing' || props.gameStatus === 'paused'
);
const modeShortLabel = computed(() => (props.mode === 'timed' ? t.timed : t.endless));
const timeLabel = computed(() => (props.mode === 'timed' ? t.remaining : t.elapsed));
const timeValue = computed(() =>
  props.mode === 'timed' ? `${props.remainingSec}s` : `${props.elapsedSec}s`
);
const timeHelper = computed(() => (props.mode === 'timed' ? '倒计时' : '累计'));
</script>

<style scoped>
.match3-hud {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.match3-actions {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.match3-actions .side-action:first-child {
  margin-top: 0;
}

.game-mode-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}

.game-mode-tab {
  flex: 1 1 auto;
  min-width: 0;
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(15, 23, 42, 0.55);
  color: rgba(148, 163, 184, 0.92);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
  cursor: pointer;
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.game-mode-tab:hover:not(:disabled) {
  border-color: rgba(96, 165, 250, 0.45);
  color: rgba(226, 232, 240, 0.95);
  background: rgba(30, 41, 59, 0.75);
}

.game-mode-tab--active {
  border-color: rgba(96, 165, 250, 0.75);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.42), rgba(37, 99, 235, 0.32));
  color: #f8fafc;
  box-shadow:
    0 0 0 1px rgba(147, 197, 253, 0.35),
    0 6px 16px rgba(37, 99, 235, 0.28);
}

.game-mode-tab:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
