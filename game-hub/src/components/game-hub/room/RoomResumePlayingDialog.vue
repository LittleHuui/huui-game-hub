<template>
  <AppModal :visible="visible" :title="title" @close="$emit('cancel')">
    <div class="room-hub-form">
      <p class="muted-small">{{ message }}</p>
      <p v-if="errorMessage" class="empty-text">{{ errorMessage }}</p>
      <div class="room-hub-form__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--ghost game-action-btn--sm"
          :disabled="submitting"
          @click="$emit('cancel')"
        >
          {{ cancelText }}
        </button>
        <button
          type="button"
          class="game-action-btn game-action-btn--primary game-action-btn--sm"
          :disabled="submitting"
          @click="$emit('confirm')"
        >
          {{ submitting ? confirmLoadingText : confirmText }}
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
  title: { type: String, default: '回到对局' },
  message: {
    type: String,
    default: '你有正在进行的对局，是否回到对局？'
  },
  confirmText: { type: String, default: '回到对局' },
  cancelText: { type: String, default: '退出房间' },
  confirmLoadingText: { type: String, default: '处理中…' },
  submitting: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' }
});

defineEmits(['confirm', 'cancel']);
</script>
