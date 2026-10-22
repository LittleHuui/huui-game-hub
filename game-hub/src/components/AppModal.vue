<template>
  <div v-if="visible" v-viewport-backdrop class="modal-mask" @click.self="onMaskClick">
    <div ref="dialog" class="modal" tabindex="-1" role="dialog" aria-modal="true" :aria-label="title || undefined" @click.stop>
      <header class="modal-header">
        <h2 class="modal-header__title">
          <slot name="title">
            {{ title }}
          </slot>
        </h2>
        <button
          v-if="closable"
          type="button"
          class="modal-close-btn"
          aria-label="关闭"
          @click="emitClose"
        >
          <AppIcon name="close" :size="16" />
        </button>
      </header>
      <section class="modal-body hub-scrollbar">
        <slot />
      </section>
      <footer v-if="$slots.footer" class="modal-footer">
        <slot name="footer" />
      </footer>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import AppIcon from './ui/AppIcon.vue';
import vViewportBackdrop from './ui/viewportBackdrop.js';
const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  closable: { type: Boolean, default: true },
  maskClosable: { type: Boolean, default: true }
});

const emit = defineEmits(['close']);
const dialog = ref(null);
let restoreFocus = null;
function onKeydown(event) {
  if (!props.visible || !dialog.value || !dialog.value.contains(document.activeElement)) return;
  if (event.key === 'Escape') { event.preventDefault(); emitClose(); }
  if (event.key !== 'Tab') return;
  const nodes = [...dialog.value.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]')].filter(el => el.getClientRects().length);
  if (!nodes.length) { event.preventDefault(); dialog.value.focus(); return; }
  const first = nodes[0], last = nodes[nodes.length - 1];
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
watch(() => props.visible, async visible => {
  if (visible) {
    restoreFocus = document.activeElement;
    document.addEventListener('keydown', onKeydown);
    await nextTick(); dialog.value?.focus();
  } else {
    document.removeEventListener('keydown', onKeydown);
    if (restoreFocus?.isConnected) restoreFocus.focus();
  }
}, { immediate: true });
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown));

function emitClose() {
  if (!props.closable) {
    return;
  }
  emit('close');
}

function onMaskClick() {
  if (!props.maskClosable || !props.closable) {
    return;
  }
  emit('close');
}
</script>
