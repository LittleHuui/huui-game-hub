<template>
  <div class="toast-stack" aria-live="polite">
    <div v-for="t in toast.items" :key="t.id" :class="toastRowClass(t)">
      <span v-if="t.toastKind === 'hint-safe' || t.toastKind === 'hint-mine'" class="toast-hint-glyph">
        {{ t.toastKind === 'hint-safe' ? '✓' : '✕' }}
      </span>
      <div class="toast-hint-body">
        <span class="toast-level">{{ toastLevelLine(t) }}</span>
        {{ t.message }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { useToastStore } from '../stores/toastStore.js';

const toast = useToastStore();

function toastRowClass(t) {
  if (t.toastKind === 'hint-safe') {
    return { toast: true, 'toast--hint-safe': true };
  }
  if (t.toastKind === 'hint-mine') {
    return { toast: true, 'toast--hint-mine': true };
  }
  return { toast: true, [`toast--${t.level || 'info'}`]: true };
}

function toastLevelLine(t) {
  if (t.toastKind === 'hint-safe') {
    return '安全格';
  }
  if (t.toastKind === 'hint-mine') {
    return '危险格';
  }
  const map = { info: '信息', success: '成功', warning: '提醒', error: '错误' };
  return map[t.level] || '信息';
}
</script>
