<template>
  <section ref="panel" class="room-hub-panel">
    <p v-if="loading && rooms.length === 0" class="empty-text">正在加载房间列表…</p>
    <p v-else-if="errorMessage" class="empty-text">{{ errorMessage }}</p>
    <p v-else-if="rooms.length === 0" class="empty-text">{{ emptyText }}</p>
    <div v-else class="room-hub-list">
      <RoomCard
        v-for="room in pagedRooms"
        :key="room.roomId"
        :room="room"
        :room-config-schema="roomConfigSchema"
        :disabled="disabled"
        @select="!disabled && $emit('select-room', room)"
      />
    </div>
    <nav v-if="!loading && !errorMessage && rooms.length > 0" class="room-hub-pager" aria-label="房间分页">
      <span>共 {{ rooms.length }} 个房间</span>
      <div v-if="pageCount > 1" class="room-hub-pager__actions">
        <button type="button" aria-label="上一页" :disabled="page === 1" @click="page--"><AppIcon name="arrow-left" :size="15" /></button>
        <span>{{ page }} / {{ pageCount }}</span>
        <button type="button" aria-label="下一页" :disabled="page === pageCount" @click="page++"><AppIcon name="arrow-right" :size="15" /></button>
      </div>
    </nav>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import RoomCard from './RoomCard.vue';
import AppIcon from '../../ui/AppIcon.vue';

const props = defineProps({
  rooms: { type: Array, default: () => [] },
  resetKey: { type: String, default: '' },
  roomConfigSchema: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  emptyText: { type: String, default: '暂无房间，创建第一个房间吧' }
});

defineEmits(['select-room']);
const panel = ref(null);
const page = ref(1);
const pageSize = ref(6);
const pageCount = computed(() => Math.max(1, Math.ceil(props.rooms.length / pageSize.value)));
const pagedRooms = computed(() => props.rooms.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));
function readPageSize() {
  if (!panel.value) return;
  pageSize.value = Number(window.getComputedStyle(panel.value).getPropertyValue('--gh-room-page-size')) || 6;
}
watch(() => props.resetKey, () => { page.value = 1; });
watch(pageCount, count => { page.value = Math.min(page.value, count); });
onMounted(() => { readPageSize(); window.addEventListener('resize', readPageSize); });
onBeforeUnmount(() => window.removeEventListener('resize', readPageSize));
</script>
