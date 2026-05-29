<template>
  <AppModal :visible="visible" title="房间详情" @close="$emit('close')">
    <div v-if="room" class="room-hub-detail">
      <dl class="room-hub-detail__section">
        <div class="room-hub-detail__row">
          <dt>房间名称</dt>
          <dd>{{ roomName }}</dd>
        </div>
        <div class="room-hub-detail__row">
          <dt>房主</dt>
          <dd>{{ ownerNickname }}</dd>
        </div>
        <div class="room-hub-detail__row">
          <dt>人数</dt>
          <dd>{{ memberCount }} / {{ maxPlayers }}</dd>
        </div>
        <div class="room-hub-detail__row">
          <dt>状态</dt>
          <dd>{{ statusLabel }}</dd>
        </div>
      </dl>

      <section v-if="configRows.length > 0" class="room-hub-detail__section">
        <h3 class="room-hub-detail__section-title">房间配置</h3>
        <dl class="room-hub-detail__config">
          <div v-for="row in configRows" :key="row.label" class="room-hub-detail__row">
            <dt>{{ row.label }}</dt>
            <dd>{{ row.value }}</dd>
          </div>
        </dl>
      </section>
      <p v-else class="muted-small room-hub-detail__empty-config">暂无额外配置项</p>
    </div>

    <div v-if="showActions" class="room-hub-form__actions room-hub-detail__actions">
      <button
        type="button"
        class="game-action-btn game-action-btn--primary game-action-btn--sm"
        :disabled="primaryActionDisabled || primaryActionLoading"
        @click="$emit('primary-action')"
      >
        {{ primaryActionLoading ? primaryActionLoadingText : primaryActionText }}
      </button>
    </div>
  </AppModal>
</template>

<script setup>
import { computed } from 'vue';
import AppModal from '../../AppModal.vue';
import { buildRoomConfigDisplayRows } from '../../../utils/roomConfigFormUtils.js';
import './roomHub.css';

const props = defineProps({
  visible: { type: Boolean, default: false },
  room: { type: Object, default: null },
  roomConfigSchema: { type: Array, default: () => [] },
  /** list：展示主操作；waiting：只读 */
  scene: {
    type: String,
    default: 'waiting',
    validator: (value) => ['list', 'waiting'].includes(value)
  },
  primaryActionText: { type: String, default: '加入房间' },
  primaryActionDisabled: { type: Boolean, default: false },
  primaryActionLoading: { type: Boolean, default: false },
  primaryActionLoadingText: { type: String, default: '处理中…' }
});

defineEmits(['close', 'primary-action']);

const STATUS_LABELS = Object.freeze({
  waiting: '等待中',
  playing: '对局中'
});

const showPrimaryAction = computed(() => props.scene === 'list');
const hasPrimaryActionText = computed(() => String(props.primaryActionText || '').trim().length > 0);
const showActions = computed(() => showPrimaryAction.value && hasPrimaryActionText.value);
const roomName = computed(() => String(props.room?.roomName || '').trim() || '房间');
const ownerNickname = computed(() => String(props.room?.ownerNickname || '').trim() || '—');
const memberCount = computed(() => Number(props.room?.memberCount) || 0);
const maxPlayers = computed(() => Number(props.room?.maxPlayers) || 0);
const statusLabel = computed(
  () => STATUS_LABELS[props.room?.status] || props.room?.status || '未知'
);

const configRows = computed(() =>
  buildRoomConfigDisplayRows(props.roomConfigSchema, props.room?.roomConfig)
);
</script>
