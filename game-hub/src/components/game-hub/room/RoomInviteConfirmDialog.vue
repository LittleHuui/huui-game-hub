<template>
  <AppModal :visible="visible" title="房间邀请" @close="$emit('reject')">
    <div class="room-hub-form">
      <p class="muted-small">
        <strong>{{ inviterNickname }}</strong> 邀请你加入 <strong>{{ roomName }}</strong>
      </p>
      <p v-if="errorMessage" class="empty-text">{{ errorMessage }}</p>
      <div class="room-hub-form__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--secondary game-action-btn--sm"
          :disabled="submitting"
          @click="$emit('reject')"
        >
          拒绝
        </button>
        <button
          type="button"
          class="game-action-btn game-action-btn--primary game-action-btn--sm"
          :disabled="submitting"
          @click="$emit('accept')"
        >
          同意
        </button>
      </div>
    </div>
  </AppModal>
</template>

<script setup>
import AppModal from '../../AppModal.vue';
import './roomHub.css';

defineProps({
  visible: { type: Boolean, default: false },
  roomName: { type: String, default: '房间' },
  inviterNickname: { type: String, default: '玩家' },
  submitting: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' }
});

defineEmits(['accept', 'reject']);
</script>
