<template>
  <div v-if="visible" class="modal-mask" @click.self="onMaskClick">
    <div class="modal" role="dialog" aria-modal="true" @click.stop>
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
          ×
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
const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  closable: { type: Boolean, default: true },
  maskClosable: { type: Boolean, default: true }
});

const emit = defineEmits(['close']);

function emitClose() {
  if (!props.closable) {
    return;
  }
  emit('close');
}

function onMaskClick() {
  if (!props.maskClosable) {
    return;
  }
  emit('close');
}
</script>
