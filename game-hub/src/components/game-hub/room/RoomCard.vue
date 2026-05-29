<template>
  <button
    type="button"
    class="room-hub-card"
    :disabled="disabled"
    @click="$emit('select', room)"
  >
    <div class="room-hub-card__title-row">
      <h3 class="room-hub-card__title">{{ room.roomName }}</h3>
      <span class="room-hub-card__status" :class="statusClass">{{ statusLabel }}</span>
    </div>
    <dl class="room-hub-card__meta">
      <div class="room-hub-card__meta-row">
        <dt>房主</dt>
        <dd>{{ room.ownerNickname }}</dd>
      </div>
      <div class="room-hub-card__meta-row">
        <dt>人数</dt>
        <dd>{{ room.memberCount }} / {{ room.maxPlayers }}</dd>
      </div>
      <div class="room-hub-card__meta-row room-hub-card__meta-row--summary">
        <dt>配置</dt>
        <dd>{{ configSummary }}</dd>
      </div>
    </dl>
  </button>
</template>

<script setup>
import { computed } from 'vue';
import { buildRoomConfigSummaryText } from '../../../utils/roomConfigFormUtils.js';
import './roomHub.css';

const props = defineProps({
  /** @type {import('vue').PropType<{ roomName: string; ownerNickname: string; memberCount: number; maxPlayers: number; status: string; mode?: string; roomConfig?: object }>} */
  room: {
    type: Object,
    required: true
  },
  roomConfigSchema: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
});

defineEmits(['select']);

const STATUS_LABELS = Object.freeze({
  waiting: '等待中',
  playing: '对局中'
});

const statusLabel = computed(() => STATUS_LABELS[props.room.status] || props.room.status || '未知');
const statusClass = computed(() => {
  const status = props.room.status;
  if (status === 'playing') {
    return 'room-hub-card__status--playing';
  }
  return '';
});

const configSummary = computed(() =>
  buildRoomConfigSummaryText(props.roomConfigSchema, props.room.roomConfig, props.room.mode)
);
</script>
