<template>
  <div v-if="visible" class="match3-result-mask">
    <div class="match3-result-card">
      <h2>本局结算</h2>
      <p>{{ deadBoard ? '棋盘已无可用步数，对局结束' : '对局已结束' }}</p>
      <div class="match3-result-grid">
        <span>模式</span><strong>{{ mode === 'timed' ? '限时' : '无尽' }}</strong>
        <span>得分</span><strong>{{ score }}</strong>
        <span>奖励</span><strong>{{ reward }}</strong>
        <span>步数</span><strong>{{ moves }}</strong>
        <span>最大连击</span><strong>{{ comboMax }}</strong>
      </div>
      <button type="button" class="success" @click="$emit('close')">确定</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, required: true },
  mode: { type: String, required: true },
  score: { type: Number, required: true },
  reward: { type: Number, required: true },
  moves: { type: Number, required: true },
  comboMax: { type: Number, required: true },
  deadBoard: { type: Boolean, required: true }
});

defineEmits(['close']);
</script>

<style scoped>
.match3-result-mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(2, 6, 23, 0.72);
}

.match3-result-card {
  width: min(420px, calc(100vw - 32px));
  padding: 24px;
  border-radius: 24px;
  background: #111827;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
}

.match3-result-card h2 {
  margin-top: 0;
}

.match3-result-grid {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  margin: 18px 0;
}
</style>
