<template>
  <section v-if="room || errorMessage" class="room-hub-panel" aria-label="我的活跃房间">
    <template v-if="room">
      <p class="muted-small">
        我的活跃房间：{{ gameName || room.gameCode || '未知游戏' }} · {{ room.roomName || room.roomId }}
        （{{ statusLabel }}）
      </p>
      <div class="room-hub-form__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--ghost game-action-btn--sm"
          :disabled="disabled"
          @click="$emit('leave')"
        >
          退出房间
        </button>
        <button
          type="button"
          class="game-action-btn game-action-btn--secondary game-action-btn--sm"
          :disabled="disabled"
          @click="$emit('return')"
        >
          {{ room.status === 'playing' ? '回到对局' : '返回房间' }}
        </button>
      </div>
    </template>
    <p v-if="errorMessage" class="empty-text" role="alert">{{ errorMessage }}</p>
  </section>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  room: { type: Object, default: null },
  gameName: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' }
});

defineEmits(['return', 'leave']);

const statusLabel = computed(() => ({ waiting: '等待中', playing: '对局中' })[props.room?.status] || '状态待确认');
</script>
