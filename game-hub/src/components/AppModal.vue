<template>
  <div v-if="visible" class="modal-mask" @click.self="$emit('close')">
    <div class="modal hub-scrollbar" @click.stop>
      <div class="modal-header">
        <h2 class="modal-header__title">{{ title }}</h2>
        <button
          type="button"
          class="modal-close-btn"
          aria-label="关闭"
          @click="$emit('close')"
        >
          ×
        </button>
      </div>
      <div class="modal-body">
        <slot />
      </div>
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
