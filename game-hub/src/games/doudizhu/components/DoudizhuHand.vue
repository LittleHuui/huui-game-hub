<template>
  <div
    class="doudizhu-hand"
    :class="{ 'doudizhu-hand--disabled': disabled || busy }"
  >
    <SelectableItemHand
      :items="handItems"
      :selected-item-ids="selectedItemIds"
      :selectable-item-ids="selectableItemIds"
      :disabled-item-ids="disabledItemIds"
      :disabled="disabled"
      :busy="busy"
      :multiple="true"
      :stack-items="true"
      @change="$emit('change', $event)"
      @illegal-click="$emit('illegal-click', $event)"
    >
      <template #item="{ item, selected }">
        <DoudizhuCard :card="item.card" :selected="selected" />
      </template>
    </SelectableItemHand>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { SelectableItemHand } from '../../../components/game/index.js';
import DoudizhuCard from './DoudizhuCard.vue';

const props = defineProps({
  handCards: {
    type: Array,
    default: () => []
  },
  selectedItemIds: {
    type: Array,
    default: () => []
  },
  selectableItemIds: {
    type: Array,
    default: () => []
  },
  disabledItemIds: {
    type: Array,
    default: () => []
  },
  disabled: {
    type: Boolean,
    default: false
  },
  busy: {
    type: Boolean,
    default: false
  }
});

defineEmits(['change', 'illegal-click']);

const handItems = computed(() =>
  (props.handCards || [])
    .map((card) => ({
      id: String(card?.cardInstanceId || '').trim(),
      card
    }))
    .filter((item) => item.id)
);
</script>
