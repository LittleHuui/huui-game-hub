<template>
  <AppModal :visible="visible" title="踩到地雷" @close="$emit('decline')">
    <p>使用复活卡继续本局，或等待倒计时结束放弃复活。</p>
    <div class="revive-countdown" role="timer">{{ secondsLeft }} 秒</div>
    <template #footer>
      <button type="button" class="secondary" @click="$emit('decline')">放弃复活</button>
      <button type="button" class="gh-primary" :disabled="reviveDisabled" @click="$emit('confirm')">使用复活卡</button>
    </template>
  </AppModal>
</template>
<script setup>
import AppModal from '../../../components/AppModal.vue';
defineProps({
  visible: { type: Boolean, required: true },
  secondsLeft: { type: Number, required: true },
  reviveDisabled: { type: Boolean, required: true }
});
defineEmits(['confirm', 'decline']);
</script>
