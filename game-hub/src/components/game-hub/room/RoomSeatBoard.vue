<template>
  <div class="room-seat-board">
    <div
      v-for="(row, rowIndex) in seatRows"
      :key="rowIndex"
      class="room-seat-board__row"
      :class="{ 'room-seat-board__row--stagger': rowIndex % 2 === 1 }"
    >
      <template v-for="(item, itemIndex) in row" :key="itemKey(item, rowIndex, itemIndex)">
        <button
          v-if="item.type === 'add'"
          type="button"
          class="room-seat-add"
          :disabled="disabled"
          aria-label="添加玩家"
          @click="$emit('add-click')"
        >
          <span class="room-seat-add__circle" aria-hidden="true">+</span>
          <span class="room-seat-add__label">邀请</span>
        </button>
        <RoomSeatAvatar
          v-else
          :nickname="item.nickname"
          :avatar="item.avatar"
          :is-owner="item.isOwner"
          :is-ai="item.isAi"
          :is-managed="item.isManaged"
          :managed-reason="item.managedReason"
          :show-managed-badge="showManagedBadge"
          :removable="canRemoveSeat(item)"
          :remove-disabled="disabled"
          @remove="$emit('remove-member', item.playerId)"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import RoomSeatAvatar from './RoomSeatAvatar.vue';
import './roomHub.css';

const props = defineProps({
  seats: { type: Array, default: () => [] },
  maxSeatsPerRow: { type: Number, default: 5 },
  showAddSlot: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  showManagedBadge: { type: Boolean, default: false },
  removablePlayerIds: { type: Array, default: () => [] }
});

defineEmits(['add-click', 'remove-member']);

/**
 * @param {object} seat
 * @returns {boolean}
 */
function canRemoveSeat(seat) {
  const playerId = String(seat?.playerId || '').trim();
  if (!playerId) {
    return false;
  }
  return (props.removablePlayerIds || []).includes(playerId);
}

/**
 * @param {object} item
 * @param {number} rowIndex
 * @param {number} itemIndex
 */
function itemKey(item, rowIndex, itemIndex) {
  if (item.type === 'add') {
    return `add-${rowIndex}-${itemIndex}`;
  }
  return item.playerId || `seat-${rowIndex}-${itemIndex}`;
}

/**
 * @param {object[]} items
 * @param {number} size
 */
function chunkItems(items, size) {
  const limit = Math.max(1, Number(size) || 5);
  const rows = [];
  for (let index = 0; index < items.length; index += limit) {
    rows.push(items.slice(index, index + limit));
  }
  return rows;
}

const seatRows = computed(() => {
  const members = Array.isArray(props.seats) ? props.seats : [];
  const items = members.map((seat) => ({ ...seat, type: 'seat' }));
  if (props.showAddSlot) {
    items.push({ type: 'add' });
  }
  return chunkItems(items, props.maxSeatsPerRow);
});
</script>
