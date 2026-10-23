<template>
  <div class="room-hub-page">
    <AppPageHeader :title="title">
      <template #actions><button type="button" class="gh-primary" :disabled="disabled || loading" @click="$emit('create')"><AppIcon name="plus" :size="16" />创建房间</button></template>
    </AppPageHeader>
    <div class="room-hub-searchbar">
      <label class="room-hub-search"><AppIcon name="search" :size="17" /><input v-model="searchKeyword" type="search" placeholder="搜索房间或房主" aria-label="搜索房间" :disabled="disabled || loading" /></label>
      <button type="button" :disabled="disabled || loading" @click="$emit('refresh')"><AppIcon name="refresh" :size="16" /><span>刷新</span></button>
    </div>

    <slot />

    <RoomListPanel
      :rooms="filteredRooms"
      :reset-key="searchKeyword"
      :loading="loading"
      :disabled="disabled || loading"
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
import AppPageHeader from '../../ui/AppPageHeader.vue';
import AppIcon from '../../ui/AppIcon.vue';

const props = defineProps({
  title: { type: String, default: '房间列表' },
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
