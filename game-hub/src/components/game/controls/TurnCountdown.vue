<template>
  <span
    class="turn-countdown"
    :class="{
      'turn-countdown--compact': compact,
      'turn-countdown--urgent': isUrgent,
      'turn-countdown--inactive': displaySeconds == null
    }"
    :title="titleText"
  >
    <span class="turn-countdown__icon" aria-hidden="true">⏰</span>
    <span class="turn-countdown__value">{{ displayText }}</span>
  </span>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue';
import './turnGame.css';

const props = defineProps({
  /** 剩余秒数（静态展示，不与 expiresAtMs 混用） */
  seconds: {
    type: Number,
    default: null
  },
  /** 截止 Unix 毫秒时间戳 */
  expiresAtMs: {
    type: Number,
    default: null
  },
  compact: {
    type: Boolean,
    default: false
  },
  /** 低于该秒数时使用紧急样式 */
  urgentBelowSeconds: {
    type: Number,
    default: 10
  }
});

const nowMs = ref(Date.now());
let tickTimer = null;

/**
 * 清理倒计时定时器。
 */
function clearTickTimer() {
  if (tickTimer != null) {
    clearInterval(tickTimer);
    tickTimer = null;
  }
}

/**
 * 按 expiresAtMs 启动每秒刷新。
 */
function syncTickTimer() {
  clearTickTimer();
  if (props.expiresAtMs == null || !Number.isFinite(props.expiresAtMs)) {
    return;
  }
  nowMs.value = Date.now();
  tickTimer = setInterval(() => {
    nowMs.value = Date.now();
  }, 1000);
}

watch(
  () => props.expiresAtMs,
  () => {
    syncTickTimer();
  },
  { immediate: true }
);

onUnmounted(() => {
  clearTickTimer();
});

/**
 * 计算展示用剩余秒数。
 */
const displaySeconds = computed(() => {
  if (props.expiresAtMs != null && Number.isFinite(props.expiresAtMs)) {
    const diff = props.expiresAtMs - nowMs.value;
    return Math.max(0, Math.ceil(diff / 1000));
  }
  if (props.seconds != null && Number.isFinite(props.seconds)) {
    return Math.max(0, Math.ceil(props.seconds));
  }
  return null;
});

const displayText = computed(() => {
  if (displaySeconds.value == null) {
    return '—';
  }
  return String(displaySeconds.value);
});

const isUrgent = computed(() => {
  if (displaySeconds.value == null) {
    return false;
  }
  const threshold = Number(props.urgentBelowSeconds);
  if (!Number.isFinite(threshold)) {
    return false;
  }
  return displaySeconds.value <= threshold;
});

const titleText = computed(() => {
  if (displaySeconds.value == null) {
    return '无倒计时';
  }
  return `剩余 ${displaySeconds.value} 秒`;
});
</script>
