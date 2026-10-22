<template>
  <AppModal :visible="visible" :title="title" :closable="!disabled" :mask-closable="!disabled" @close="onCancel">
    <div class="uno-color-picker">
      <p v-if="description" class="muted-small uno-color-picker__description">{{ description }}</p>
      <div class="uno-color-picker__options">
        <button
          v-for="option in colorOptions"
          :key="option.key"
          type="button"
          class="uno-color-picker__option"
          :class="`uno-color-picker__option--${option.value}`"
          :disabled="disabled"
          :aria-label="option.label"
          @click="onSelect(option)"
        >
          {{ option.label }}
        </button>
      </div>
      <button
        type="button"
        class="game-action-btn game-action-btn--secondary game-action-btn--sm uno-color-picker__cancel"
        :disabled="disabled"
        @click="onCancel"
      >
        取消
      </button>
    </div>
  </AppModal>
</template>

<script setup>
import AppModal from '../../../components/AppModal.vue';
import { UNO_COLOR_OPTIONS } from '../unoGameConstants.js';

defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '选择颜色'
  },
  description: {
    type: String,
    default: '万能牌须指定生效花色'
  },
  disabled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['select', 'cancel']);

const colorOptions = UNO_COLOR_OPTIONS;

/**
 * @param {{ key: string; value: string; label: string }} option
 */
function onSelect(option) {
  emit('select', { color: option.value, colorKey: option.key });
}

function onCancel() {
  emit('cancel');
}
</script>
