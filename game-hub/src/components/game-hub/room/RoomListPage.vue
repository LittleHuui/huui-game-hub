<template>
  <div class="room-hub-page">
    <header class="room-hub-page__toolbar">
      <div class="room-hub-page__toolbar-main">
        <h2 class="room-hub-page__title">{{ title }}</h2>
        <p v-if="subtitle" class="room-hub-page__subtitle muted-small">{{ subtitle }}</p>
      </div>
      <div class="room-hub-page__toolbar-actions">
        <input
          v-model="searchKeyword"
          type="search"
          class="room-hub-page__search"
          placeholder="搜索房间名称"
          :disabled="disabled || loading"
          aria-label="搜索房间"
        />
        <button
          type="button"
          class="game-action-btn game-action-btn--ghost game-action-btn--sm"
          :disabled="loading"
          @click="$emit('refresh')"
        >
          刷新
        </button>
        <button
          type="button"
          class="game-action-btn game-action-btn--primary game-action-btn--sm"
          :disabled="disabled || loading"
          @click="$emit('create')"
        >
          创建房间
        </button>
      </div>
    </header>

    <RoomListPanel
      :rooms="filteredRooms"
      :loading="loading"
      :disabled="disabled"
      :error-message="errorMessage"
      :room-config-schema="roomConfigSchema"
      :empty-text="emptyText"
      @select-room="$emit('select-room', $event)"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import RoomListPanel from './RoomListPanel.vue';
import './roomHub.css';

const props = defineProps({
  title: { type: String, default: '房间列表' },
  subtitle: { type: String, default: '' },
  gameCode: { type: String, default: '' },
  rooms: { type: Array, default: () => [] },
  roomConfigSchema: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  emptyText: { type: String, default: '暂无房间，创建第一个房间吧' }
});

defineEmits(['refresh', 'create', 'select-room']);

const searchKeyword = ref('');

const filteredRooms = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase();
  const list = Array.isArray(props.rooms) ? props.rooms : [];
  if (!keyword) {
    return list;
  }
  return list.filter((room) => {
    const name = String(room?.roomName || '').trim().toLowerCase();
    const owner = String(room?.ownerNickname || '').trim().toLowerCase();
    return name.includes(keyword) || owner.includes(keyword);
  });
});
</script>
