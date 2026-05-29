<template>
  <AppModal :visible="visible" title="邀请在线用户" @close="$emit('close')">
    <div class="room-hub-form">
      <p v-if="disabled" class="empty-text">房间已满，无法继续邀请。</p>
      <p v-else-if="loading" class="empty-text">正在加载在线用户…</p>
      <p v-else-if="errorMessage" class="empty-text">{{ errorMessage }}</p>
      <p v-else-if="users.length === 0" class="empty-text">暂无可邀请的在线用户</p>

      <div v-else class="room-invite-list hub-scrollbar">
        <div v-for="user in users" :key="user.serviceId" class="room-invite-row">
          <span class="room-invite-row__avatar" aria-hidden="true">{{ user.nickname.charAt(0) }}</span>
          <span class="room-invite-row__name">{{ user.nickname }}</span>
          <button
            type="button"
            class="game-action-btn game-action-btn--primary game-action-btn--sm"
            :disabled="submitting"
            @click="$emit('invite', user)"
          >
            邀请
          </button>
        </div>
      </div>

      <div class="room-hub-form__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--secondary game-action-btn--sm"
          :disabled="submitting"
          @click="$emit('close')"
        >
          关闭
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
  users: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' }
});

defineEmits(['close', 'invite']);
</script>
