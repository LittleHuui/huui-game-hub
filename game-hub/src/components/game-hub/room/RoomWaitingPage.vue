<template>
  <div class="room-hub-page room-hub-page--waiting">
    <AppPageHeader :title="roomName" :meta="`${memberCount} / ${maxPlayers} 人 · ${statusText}`">
      <template #actions><span class="room-hub-status">{{ statusText }}</span><AppMenu label="房间操作" title="房间" :disabled="actionsDisabled" :items="roomMenuItems" @select="emit($event)" /></template>
    </AppPageHeader>

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
import AppPageHeader from '../../ui/AppPageHeader.vue';
import AppMenu from '../../ui/AppMenu.vue';

const props = defineProps({
  room: { type: Object, default: null },
  currentPlayerId: { type: String, default: '' },
  roomRule: { type: Object, default: null },
  actionsDisabled: { type: Boolean, default: false }
});

const emit = defineEmits(['detail', 'leave', 'invite', 'start', 'add-ai', 'settings', 'remove-member']);
const roomMenuItems = computed(() => [
  ...(showRoomSettings.value ? [{ id: 'settings', label: '房间设置', icon: 'settings' }] : []),
  { id: 'detail', label: '房间详情', icon: 'info' },
  { id: 'leave', label: '离开房间', icon: 'logout', danger: true }
]);

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
