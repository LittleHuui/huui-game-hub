<template>
  <div v-if="visible" class="modal-mask" @click.self="$emit('close')">
    <div class="modal hub-scrollbar" @click.stop>
      <div class="modal-header">
        <h2>{{ title }}</h2>
        <button type="button" class="danger" @click="$emit('close')">关闭</button>
      </div>
      <slot />
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
