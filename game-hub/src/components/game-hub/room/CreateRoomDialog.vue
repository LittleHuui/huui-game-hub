<template>
  <AppModal :visible="visible" title="创建房间" @close="$emit('close')">
    <form class="room-hub-form" @submit.prevent="onSubmit">
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
        :field="toControlField(field)"
        @change="onConfigFieldChange"
      />

      <div v-for="field in visibleNumberFields" :key="field.key" class="room-hub-form__field">
        <label :for="`room-hub-${field.key}`">{{ field.label }}</label>
        <input
          :id="`room-hub-${field.key}`"
          v-model.number="fieldValues[field.key]"
          type="number"
          :min="field.min"
          :max="field.max"
          :disabled="submitting"
        />
        <p v-if="field.description" class="muted-small">{{ field.description }}</p>
      </div>

      <p v-if="errorMessage" class="empty-text">{{ errorMessage }}</p>

      <div class="room-hub-form__actions">
        <button type="button" class="game-action-btn game-action-btn--secondary game-action-btn--sm" :disabled="submitting" @click="$emit('close')">
          取消
        </button>
        <button type="submit" class="game-action-btn game-action-btn--primary game-action-btn--sm" :disabled="submitting">
          {{ submitting ? '创建中…' : '创建' }}
        </button>
      </div>
    </form>
  </AppModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import AppModal from '../../AppModal.vue';
import { GameControlField, GAME_CONTROL_TYPE } from '../../game/index.js';
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
 * @param {{ key: string; controlType: string; label: string; value: unknown; options?: Array }} field
 */
function toControlField(field) {
  const value = fieldValues.value[field.key];
  if (field.controlType === 'switch') {
    return {
      key: field.key,
      type: GAME_CONTROL_TYPE.SWITCH,
      label: field.label,
      value: Boolean(value)
    };
  }
  if (field.controlType === 'radio') {
    return {
      key: field.key,
      type: GAME_CONTROL_TYPE.RADIO,
      label: field.label,
      value,
      options: field.options || []
    };
  }
  if (field.controlType === 'select') {
    return {
      key: field.key,
      type: GAME_CONTROL_TYPE.SELECT,
      label: field.label,
      value,
      options: field.options || []
    };
  }
  return {
    key: field.key,
    type: GAME_CONTROL_TYPE.CUSTOM,
    label: field.label,
    value
  };
}

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
