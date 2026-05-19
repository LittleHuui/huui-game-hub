<template>
  <div v-if="visible" class="modal-mask revive-offer-mask" @click.self="$emit('decline')">
    <div class="modal" @click.stop>
      <h2 style="margin-bottom: 8px">踩到地雷</h2>
      <p>是否使用复活卡复活本局？也可等待倒计时结束放弃复活。</p>
      <div class="revive-countdown">{{ secondsLeft }} 秒</div>
      <div class="revive-actions">
        <button type="button" class="success" :disabled="reviveDisabled" @click="$emit('confirm')">使用复活卡</button>
        <button type="button" class="danger" @click="$emit('decline')">放弃复活</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, required: true },
  secondsLeft: { type: Number, required: true },
  reviveDisabled: { type: Boolean, required: true }
});
defineEmits(['confirm', 'decline']);
</script>
