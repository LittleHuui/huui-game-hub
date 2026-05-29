<template>
  <div class="room-waiting-panel">
    <header v-if="showHeader" class="room-waiting-panel__head">
      <h2 class="room-waiting-panel__title">{{ roomName }}</h2>
      <p class="room-waiting-panel__meta muted-small">
        {{ memberCount }} / {{ maxPlayers }} 人 · {{ statusText }}
      </p>
    </header>

    <RoomSeatBoard
      :seats="seatItems"
      :max-seats-per-row="maxSeatsPerRow"
      :show-add-slot="showAddSlot"
      :disabled="actionsDisabled"
      :show-managed-badge="false"
      :removable-player-ids="removablePlayerIds"
      @add-click="$emit('invite')"
      @remove-member="$emit('remove-member', $event)"
    />

    <div v-if="!isPlaying" class="room-waiting-panel__actions">
      <button
        v-if="showAddAi"
        type="button"
        class="game-action-btn game-action-btn--ghost game-action-btn--md"
        :disabled="actionsDisabled"
        @click="$emit('add-ai')"
      >
        添加 AI
      </button>
      <button
        v-if="isOwner"
        type="button"
        class="game-action-btn game-action-btn--primary game-action-btn--md"
        :disabled="actionsDisabled || startDisabled"
        @click="$emit('start')"
      >
        开始游戏
      </button>
      <button
        v-if="showLeave"
        type="button"
        class="game-action-btn game-action-btn--warning game-action-btn--md"
        :disabled="actionsDisabled"
        @click="$emit('leave')"
      >
        离开房间
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import RoomSeatBoard from './RoomSeatBoard.vue';
import './roomHub.css';

const props = defineProps({
  room: { type: Object, default: null },
  currentPlayerId: { type: String, default: '' },
  roomRule: { type: Object, default: null },
  maxSeatsPerRow: { type: Number, default: 5 },
  actionsDisabled: { type: Boolean, default: false },
  showHeader: { type: Boolean, default: true },
  showLeave: { type: Boolean, default: true }
});

defineEmits(['invite', 'start', 'leave', 'add-ai', 'remove-member']);

const STATUS_LABELS = Object.freeze({
  waiting: '等待中',
  playing: '对局中'
});

const roomName = computed(() => String(props.room?.roomName || '').trim() || '房间');
const memberCount = computed(() => Number(props.room?.memberCount) || 0);
const maxPlayers = computed(() => Number(props.room?.maxPlayers) || 0);
const isPlaying = computed(() => props.room?.status === 'playing');
const statusText = computed(() => STATUS_LABELS[props.room?.status] || props.room?.status || '');
const isOwner = computed(() => {
  const ownerId = String(props.room?.ownerPlayerId || '').trim();
  const currentId = String(props.currentPlayerId || '').trim();
  return Boolean(ownerId && currentId && ownerId === currentId);
});
const isFull = computed(() => memberCount.value >= maxPlayers.value && maxPlayers.value > 0);
const allowAi = computed(() => {
  if (props.room?.allowAi != null) {
    return props.room.allowAi === true;
  }
  return props.roomRule?.allowAi === true;
});
const maxAiCount = computed(() => {
  if (props.room?.maxAiCount != null) {
    return Number(props.room.maxAiCount) || 0;
  }
  return Number(props.roomRule?.maxAiCount) || 0;
});
const canManageMembers = computed(
  () => !isPlaying.value && isOwner.value && props.room?.status === 'waiting'
);
const removablePlayerIds = computed(() => {
  if (!canManageMembers.value) {
    return [];
  }
  const ownerId = String(props.room?.ownerPlayerId || '').trim();
  const currentId = String(props.currentPlayerId || '').trim();
  if (!ownerId || ownerId !== currentId) {
    return [];
  }
  const members = Array.isArray(props.room?.members) ? props.room.members : [];
  return members
    .map((item) => String(item?.playerId || '').trim())
    .filter((playerId) => playerId && playerId !== ownerId);
});
const aiCount = computed(() => Number(props.room?.aiCount) || 0);
const canAddAi = computed(
  () =>
    !isPlaying.value &&
    isOwner.value &&
    props.room?.status === 'waiting' &&
    allowAi.value &&
    maxAiCount.value > 0 &&
    aiCount.value < maxAiCount.value &&
    !isFull.value
);
const showAddSlot = computed(() => !isPlaying.value && !isFull.value);
const showAddAi = computed(() => canAddAi.value);
const minPlayers = computed(() => Number(props.roomRule?.minPlayers) || 2);
const startDisabled = computed(() => memberCount.value < minPlayers.value);

const seatItems = computed(() => {
  const ownerId = String(props.room?.ownerPlayerId || '').trim();
  const members = Array.isArray(props.room?.members) ? props.room.members : [];
  return members.map((member) => ({
    playerId: member.playerId,
    nickname: member.nickname,
    avatar: member.avatar,
    isOwner: member.playerId === ownerId,
    isAi: Boolean(member.isAi),
    isManaged: Boolean(member.isManaged),
    managedReason: member.managedReason || null
  }));
});
</script>
