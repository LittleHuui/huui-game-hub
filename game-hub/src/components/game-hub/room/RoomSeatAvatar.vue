<template>
  <div class="room-seat-avatar">
    <div class="room-seat-avatar__visual">
      <button
        v-if="removable"
        type="button"
        class="room-seat-avatar__remove"
        :disabled="removeDisabled"
        aria-label="移除该座位玩家"
        @click.stop="$emit('remove')"
      >
        ×
      </button>
      <div
        class="room-seat-avatar__circle"
        :class="{
          'room-seat-avatar__circle--owner': isOwner,
          'room-seat-avatar__circle--ai': isAi
        }"
      >
        <img v-if="avatarUrl" :src="avatarUrl" :alt="nickname" />
        <span v-else aria-hidden="true">{{ avatarInitial }}</span>
      </div>
    </div>
    <span v-if="statusBadgeText" class="room-seat-avatar__badge" :class="statusBadgeClass">
      {{ statusBadgeText }}
    </span>
    <span class="room-seat-avatar__name" :title="nickname">{{ nickname }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  nickname: { type: String, default: '玩家' },
  avatar: { type: String, default: null },
  isOwner: { type: Boolean, default: false },
  isAi: { type: Boolean, default: false },
  isManaged: { type: Boolean, default: false },
  managedReason: { type: String, default: null },
  showManagedBadge: { type: Boolean, default: true },
  removable: { type: Boolean, default: false },
  removeDisabled: { type: Boolean, default: false }
});

defineEmits(['remove']);

const avatarUrl = computed(() => {
  const value = String(props.avatar || '').trim();
  return value || '';
});

const avatarInitial = computed(() => {
  const name = String(props.nickname || '').trim();
  return name ? name.charAt(0) : '?';
});

const statusBadgeText = computed(() => {
  if (props.isOwner) {
    return '房主';
  }
  if (props.isAi) {
    return 'AI';
  }
  if (props.showManagedBadge && props.isManaged) {
    return '托管';
  }
  return '';
});

const statusBadgeClass = computed(() => {
  if (props.isOwner) {
    return 'room-seat-avatar__badge--owner';
  }
  if (props.isAi) {
    return 'room-seat-avatar__badge--ai';
  }
  if (props.showManagedBadge && props.isManaged) {
    return 'room-seat-avatar__badge--managed';
  }
  return '';
});
</script>
