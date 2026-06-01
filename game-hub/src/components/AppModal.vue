<template>
  <div v-if="visible" class="modal-mask" @click.self="$emit('close')">
    <div class="modal" role="dialog" aria-modal="true" @click.stop>
      <header class="modal-header">
        <h2 class="modal-header__title">
          <slot name="title">
            {{ title }}
          </slot>
        </h2>
        <button
          type="button"
          class="modal-close-btn"
          aria-label="关闭"
          @click="$emit('close')"
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
defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' }
});
defineEmits(['close']);
</script>
