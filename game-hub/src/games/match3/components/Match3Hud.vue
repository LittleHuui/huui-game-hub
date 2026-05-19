<template>
  <div class="match3-hud" :class="`match3-hud--${section}`">
    <template v-if="section === 'config' || section === 'all'">
      <div class="muted-small">{{ t.modeSection }}</div>
      <div class="match3-mode-tabs">
        <button
          type="button"
          :class="{ active: mode === 'timed' }"
          :disabled="locked"
          @click="$emit('change-mode', 'timed')"
        >
          {{ t.timed }}
        </button>
        <button
          type="button"
          :class="{ active: mode === 'endless' }"
          :disabled="locked"
          @click="$emit('change-mode', 'endless')"
        >
          {{ t.endless }}
        </button>
      </div>
      <div class="match3-actions">
        <button type="button" class="success" @click="$emit('start')">
          {{ started ? t.restart : t.start }}
        </button>
        <button type="button" :disabled="!inProgress" @click="$emit('end')">{{ t.endGame }}</button>
      </div>
    </template>

    <template v-if="section === 'hud' || section === 'all'">
      <h2 class="match3-hud-title">{{ modeLabel }}</h2>
      <div class="match3-stats">
        <span>{{ t.score }} <strong>{{ score }}</strong></span>
        <span>{{ t.moves }} <strong>{{ moves }}</strong></span>
        <span>{{ t.comboMax }} <strong>{{ comboMax }}</strong></span>
        <span v-if="mode === 'timed'">{{ t.remaining }} <strong>{{ remainingSec }}</strong>s</span>
        <span v-else>{{ t.elapsed }} <strong>{{ elapsedSec }}</strong>s</span>
      </div>
      <p class="match3-message">{{ message }}</p>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const t = {
  modeSection: '\u6a21\u5f0f \u00b7 \u64cd\u4f5c',
  timed: '\u9650\u65f6',
  endless: '\u65e0\u9650',
  restart: '\u91cd\u65b0\u5f00\u59cb',
  start: '\u5f00\u59cb\u6e38\u620f',
  endGame: '\u7ed3\u675f\u5bf9\u5c40',
  score: '\u5f97\u5206',
  moves: '\u6b65\u6570',
  comboMax: '\u6700\u5927\u8fde\u51fb',
  remaining: '\u5269\u4f59',
  elapsed: '\u7528\u65f6',
  timedMode: '\u9650\u65f6\u6a21\u5f0f',
  endlessMode: '\u65e0\u9650\u6a21\u5f0f'
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
  started: { type: Boolean, required: true },
  inProgress: { type: Boolean, required: true },
  locked: { type: Boolean, required: true },
  message: { type: String, required: true }
});

defineEmits(['change-mode', 'start', 'end']);

const modeLabel = computed(() => (props.mode === 'timed' ? t.timedMode : t.endlessMode));
</script>

<style scoped>
.match3-hud {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.match3-hud-title {
  margin: 0;
  font-size: 1.15rem;
}

.match3-mode-tabs,
.match3-actions,
.match3-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.match3-mode-tabs button.active {
  border-color: rgba(103, 194, 58, 0.8);
  color: #bbf7d0;
}

.match3-stats span {
  min-width: 92px;
  padding: 9px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.06);
}

.match3-message {
  margin: 0;
  color: #dbeafe;
}
</style>
