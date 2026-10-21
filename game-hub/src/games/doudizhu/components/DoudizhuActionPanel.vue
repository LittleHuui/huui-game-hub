<template>
  <div class="doudizhu-action-panel">
    <div class="doudizhu-action-panel__buttons">
      <button
        v-for="action in buttonActions"
        :key="`${action.actionType}:${action.actionId}`"
        type="button"
        class="game-action-btn game-action-btn--md"
        :class="resolveButtonClass(action.actionType)"
        :disabled="isDisabled"
        @click="$emit('action', action)"
      >
        {{ resolveLabel(action.actionType) }}
      </button>
      <button
        v-if="canPlayCards"
        type="button"
        class="game-action-btn game-action-btn--primary game-action-btn--md"
        :disabled="isDisabled || !playEnabled"
        @click="$emit('play')"
      >
        出牌
      </button>
      <button
        v-if="canHint"
        type="button"
        class="game-action-btn game-action-btn--ghost game-action-btn--md"
        :disabled="isHintDisabled"
        @click="$emit('hint')"
      >
        提示
      </button>
      <slot name="middle" />
    </div>
    <p v-if="previewMessage" class="doudizhu-action-panel__preview muted-small">
      {{ previewMessage }}
    </p>
    <div
      class="doudizhu-action-panel__countdown"
      :class="{ 'doudizhu-action-panel__countdown--hidden': !showCountdown }"
    >
      <TurnCountdown
        v-if="showCountdown"
        :seconds="countdownSeconds"
        :expires-at-ms="countdownExpiresAtMs"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { TurnCountdown } from '../../../components/game/index.js';
import { formatDoudizhuActionLabel } from '../doudizhuDisplayText.js';

const props = defineProps({
  /** @type {import('vue').PropType<Array<{ actionType: string; actionId: string }>>} */
  buttonActions: { type: Array, default: () => [] },
  canPlayCards: { type: Boolean, default: false },
  previewMessage: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  playEnabled: { type: Boolean, default: false },
  hintEnabled: { type: Boolean, default: null },
  showCountdown: { type: Boolean, default: false },
  countdownSeconds: { type: Number, default: 30 },
  countdownExpiresAtMs: { type: Number, default: null }
});

defineEmits(['action', 'play', 'hint']);

const canHint = computed(() => {
  if (props.hintEnabled != null) {
    return props.hintEnabled === true;
  }
  return props.canPlayCards;
});
const isDisabled = computed(() => props.disabled || props.busy);
const isHintDisabled = computed(() => {
  if (isDisabled.value) {
    return true;
  }
  if (props.hintEnabled != null) {
    return props.hintEnabled !== true;
  }
  return false;
});

/**
 * @param {string} actionType
 * @returns {string}
 */
function resolveLabel(actionType) {
  return formatDoudizhuActionLabel(actionType);
}

/**
 * @param {string} actionType
 * @returns {string}
 */
function resolveButtonClass(actionType) {
  const type = String(actionType || '').trim();
  if (type === 'PASS' || type.startsWith('PASS_') || type === 'SKIP_SHOW_CARDS') {
    return 'game-action-btn--ghost';
  }
  if (type === 'SHOW_CARDS' || type === 'DOUBLE' || type.includes('LANDLORD') || type === 'ROB_LANDLORD') {
    return 'game-action-btn--primary';
  }
  return 'game-action-btn--secondary';
}
</script>
