<template>
  <div v-if="visible" class="game2048-result-mask">
    <div class="game2048-result-card">
      <h2>本局结算</h2>
      <p>{{ gameOver ? '无可移动方向，对局结束' : '对局已结束' }}</p>
      <div class="game2048-result-grid">
        <span>得分</span><strong>{{ score }}</strong>
        <span>平台奖励</span><strong>{{ reward }}</strong>
        <span>步数</span><strong>{{ moves }}</strong>
        <span>最大块</span><strong>{{ maxTile }}</strong>
        <span>达成 2048</span><strong>{{ reached2048 ? '是' : '否' }}</strong>
        <span v-if="clearCellUses > 0">清除锤</span>
        <strong v-if="clearCellUses > 0">{{ clearCellUses }} 次</strong>
        <span v-if="scorePenalty > 0">道具扣分</span>
        <strong v-if="scorePenalty > 0">-{{ scorePenalty }}</strong>
      </div>
      <button type="button" class="success" @click="$emit('close')">确定</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, required: true },
  score: { type: Number, required: true },
  reward: { type: Number, required: true },
  moves: { type: Number, required: true },
  maxTile: { type: Number, required: true },
  reached2048: { type: Boolean, required: true },
  clearCellUses: { type: Number, default: 0 },
  scorePenalty: { type: Number, default: 0 },
  gameOver: { type: Boolean, default: true }
});

defineEmits(['close']);
</script>
