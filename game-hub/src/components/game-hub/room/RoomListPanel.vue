<template>
  <section class="room-hub-panel">
    <p v-if="loading && rooms.length === 0" class="empty-text">正在加载房间列表…</p>
    <p v-else-if="errorMessage" class="empty-text">{{ errorMessage }}</p>
    <p v-else-if="rooms.length === 0" class="empty-text">{{ emptyText }}</p>
    <div v-else class="room-hub-list">
      <RoomCard
        v-for="room in rooms"
        :key="room.roomId"
        :room="room"
        :room-config-schema="roomConfigSchema"
        @select="$emit('select-room', room)"
      />
    </div>
  </section>
</template>

<script setup>
import RoomCard from './RoomCard.vue';
import './roomHub.css';

defineProps({
  rooms: { type: Array, default: () => [] },
  roomConfigSchema: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  emptyText: { type: String, default: '暂无房间，创建第一个房间吧' }
});

defineEmits(['select-room']);
</script>
