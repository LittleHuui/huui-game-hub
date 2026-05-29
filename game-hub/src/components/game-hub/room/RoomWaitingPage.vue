<template>
  <div class="room-hub-page room-hub-page--waiting">
    <header class="room-hub-page__toolbar">
      <div class="room-hub-page__toolbar-main">
        <h2 class="room-hub-page__title">{{ roomName }}</h2>
        <p class="room-hub-page__subtitle muted-small">
          {{ memberCount }} / {{ maxPlayers }} 人 · {{ statusText }}
        </p>
      </div>
      <div class="room-hub-page__toolbar-actions">
        <button
          v-if="showRoomSettings"
          type="button"
          class="game-action-btn game-action-btn--ghost game-action-btn--sm"
          :disabled="actionsDisabled"
          @click="$emit('settings')"
        >
          房间设置
        </button>
        <button
          type="button"
          class="game-action-btn game-action-btn--ghost game-action-btn--sm"
          :disabled="actionsDisabled"
          @click="$emit('detail')"
        >
          房间详情
        </button>
        <button
          type="button"
          class="game-action-btn game-action-btn--warning game-action-btn--sm"
          :disabled="actionsDisabled"
          @click="$emit('leave')"
        >
          离开房间
        </button>
      </div>
    </header>

    <RoomWaitingPanel
      :room="room"
      :current-player-id="currentPlayerId"
      :room-rule="roomRule"
      :actions-disabled="actionsDisabled"
      :show-header="false"
      :show-leave="false"
      @invite="$emit('invite')"
      @start="$emit('start')"
      @add-ai="$emit('add-ai')"
      @remove-member="$emit('remove-member', $event)"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue';
import RoomWaitingPanel from './RoomWaitingPanel.vue';
import './roomHub.css';

const props = defineProps({
  room: { type: Object, default: null },
  currentPlayerId: { type: String, default: '' },
  roomRule: { type: Object, default: null },
  actionsDisabled: { type: Boolean, default: false }
});

defineEmits(['detail', 'leave', 'invite', 'start', 'add-ai', 'settings', 'remove-member']);

const isOwner = computed(() => {
  const ownerId = String(props.room?.ownerPlayerId || '').trim();
  const currentId = String(props.currentPlayerId || '').trim();
  return Boolean(ownerId && currentId && ownerId === currentId);
});

const showRoomSettings = computed(
  () => isOwner.value && props.room?.status === 'waiting'
);

const STATUS_LABELS = Object.freeze({
  waiting: '等待中',
  playing: '对局中'
});

const roomName = computed(() => String(props.room?.roomName || '').trim() || '房间');
const memberCount = computed(() => Number(props.room?.memberCount) || 0);
const maxPlayers = computed(() => Number(props.room?.maxPlayers) || 0);
const statusText = computed(
  () => STATUS_LABELS[props.room?.status] || props.room?.status || ''
);
</script>
