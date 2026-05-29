<template>
  <AppModal :visible="visible" title="房间设置" @close="$emit('close')">
    <form class="room-hub-form" @submit.prevent="onSubmit">
      <div class="room-hub-form__field">
        <label for="room-settings-max-players">人数上限</label>
        <input
          id="room-settings-max-players"
          v-model.number="maxPlayersValue"
          type="number"
          :min="minMaxPlayers"
          :max="ruleMaxPlayers"
          :disabled="submitting"
        />
        <p class="muted-small">当前真人 {{ humanMemberCount }} 人，下限不可低于真人数量</p>
      </div>

      <GameControlField
        v-for="field in visibleNonNumberFields"
        :key="field.key"
        :field="toControlField(field)"
        @change="onConfigFieldChange"
      />

      <div v-for="field in visibleNumberFields" :key="field.key" class="room-hub-form__field">
        <label :for="`room-settings-${field.key}`">{{ field.label }}</label>
        <input
          :id="`room-settings-${field.key}`"
          v-model.number="fieldValues[field.key]"
          type="number"
          :min="field.min"
          :max="field.max"
          :disabled="submitting"
        />
        <p v-if="field.description" class="muted-small">{{ field.description }}</p>
      </div>

      <div class="room-hub-form__actions">
        <button
          type="submit"
          class="game-action-btn game-action-btn--primary game-action-btn--sm"
          :disabled="submitting"
        >
          {{ submitting ? '保存中…' : '保存' }}
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
  room: { type: Object, default: null },
  roomRule: { type: Object, default: null },
  roomConfigSchema: { type: Array, default: () => [] },
  submitting: { type: Boolean, default: false }
});

const emit = defineEmits(['close', 'submit']);

const maxPlayersValue = ref(2);
const fieldValues = ref({});

const ruleMaxPlayers = computed(() => Number(props.roomRule?.maxPlayers) || 10);

const humanMemberCount = computed(() => {
  const members = Array.isArray(props.room?.members) ? props.room.members : [];
  return members.filter((item) => !item?.isAi).length;
});

const minMaxPlayers = computed(() =>
  Math.max(Number(props.roomRule?.minPlayers) || 2, humanMemberCount.value)
);

const configFields = computed(() =>
  buildRoomConfigFormFields(props.roomConfigSchema, props.room?.roomConfig)
);
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
  () => [props.visible, props.room, props.roomConfigSchema],
  () => {
    if (!props.visible || !props.room) {
      return;
    }
    maxPlayersValue.value = Number(props.room.maxPlayers) || minMaxPlayers.value;
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
  const nextMaxPlayers = Number(maxPlayersValue.value) || minMaxPlayers.value;
  if (humanMemberCount.value > nextMaxPlayers) {
    emit('submit', {
      error: '当前真人玩家数已超过新的人数上限'
    });
    return;
  }
  const fields = visibleConfigFields.value.map((field) => ({
    key: field.key,
    value: fieldValues.value[field.key],
    visibleWhen: field.visibleWhen
  }));
  emit('submit', {
    maxPlayers: nextMaxPlayers,
    roomConfig: buildRoomConfigPayload(fields, fieldValues.value)
  });
}
</script>
