<template>
  <AppModal :visible="visible" title="创建房间" @close="$emit('close')">
    <form id="create-room-form" class="room-hub-form" @submit.prevent="onSubmit">
      <div class="room-hub-form__field">
        <label for="room-hub-name">房间名称</label>
        <input
          id="room-hub-name"
          v-model="roomName"
          type="text"
          maxlength="32"
          placeholder="请输入房间名称"
          :disabled="submitting"
        />
      </div>

      <GameControlField
        v-for="field in visibleNonNumberFields"
        :key="field.key"
        :field="toRoomConfigControl(field, fieldValues[field.key])"
        @change="onConfigFieldChange"
      />

      <div v-for="field in visibleNumberFields" :key="field.key" class="room-hub-form__field">
        <label :for="`room-hub-${field.key}`">{{ field.label }}</label>
        <GameNumberInput
          :input-id="`room-hub-${field.key}`"
          v-model="fieldValues[field.key]"
          :min="field.min"
          :max="field.max"
          :disabled="submitting"
        />
        <p v-if="field.description" class="muted-small">{{ field.description }}</p>
      </div>
      <p v-if="errorMessage" class="empty-text">{{ errorMessage }}</p>
      <slot name="error-action" />
    </form>
    <template #footer>
      <div class="room-hub-form__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--secondary game-action-btn--sm"
          :disabled="submitting"
          @click="$emit('close')"
        >
          取消
        </button>
        <button
          form="create-room-form"
          type="submit"
          class="game-action-btn game-action-btn--primary game-action-btn--sm"
          :disabled="submitting"
        >
          {{ submitting ? '创建中…' : '创建' }}
        </button>
      </div>
    </template>
  </AppModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import AppModal from '../../AppModal.vue';
import { GameControlField, GameNumberInput } from '../../game/index.js';
import { toRoomConfigControl } from './roomConfigControl.js';
import {
  buildRoomConfigFormFields,
  buildRoomConfigPayload,
  filterVisibleRoomConfigFields
} from '../../../utils/roomConfigFormUtils.js';
import './roomHub.css';

const props = defineProps({
  visible: { type: Boolean, default: false },
  roomConfigSchema: { type: Array, default: () => [] },
  submitting: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' }
});

const emit = defineEmits(['close', 'submit']);

const roomName = ref('');
const fieldValues = ref({});

const configFields = computed(() => buildRoomConfigFormFields(props.roomConfigSchema));
const visibleConfigFields = computed(() =>
  filterVisibleRoomConfigFields(configFields.value, fieldValues.value)
);
const visibleNonNumberFields = computed(() =>
  visibleConfigFields.value.filter((field) => field.controlType !== 'number')
);
const visibleNumberFields = computed(() =>
  visibleConfigFields.value.filter((field) => field.controlType === 'number')
);

watch(
  () => [props.visible, props.roomConfigSchema],
  () => {
    if (!props.visible) {
      return;
    }
    roomName.value = '';
    const nextValues = {};
    for (const field of configFields.value) {
      nextValues[field.key] = field.value;
    }
    fieldValues.value = nextValues;
  },
  { immediate: true }
);

/**
 * @param {{ key: string; value: unknown }} payload
 */
function onConfigFieldChange(payload) {
  if (!payload?.key) {
    return;
  }
  fieldValues.value = {
    ...fieldValues.value,
    [payload.key]: payload.value
  };
}

function onSubmit() {
  const fields = visibleConfigFields.value.map((field) => ({
    key: field.key,
    value: fieldValues.value[field.key],
    visibleWhen: field.visibleWhen
  }));
  emit('submit', {
    roomName: roomName.value.trim(),
    roomConfig: buildRoomConfigPayload(fields, fieldValues.value)
  });
}
</script>
