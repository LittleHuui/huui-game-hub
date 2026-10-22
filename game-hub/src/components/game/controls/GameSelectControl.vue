<template>
  <AppMenu class="game-select-control" :class="extraClass" :trigger-id="inputId" :disabled="disabled" :label="selectedLabel || '选择选项'" title="选择选项" :items="items" @select="onChange">
    <template #trigger><span>{{ selectedLabel }}</span><AppIcon name="chevron" :size="13" /></template>
  </AppMenu>
</template>
<script setup>
import { computed } from 'vue';
import AppMenu from '../../ui/AppMenu.vue';
import AppIcon from '../../ui/AppIcon.vue';
const props = defineProps({ modelValue: { type: [String, Number, Boolean], default: '' }, options: { type: Array, default: () => [] }, disabled: { type: Boolean, default: false }, inputId: { type: String, default: '' }, extraClass: { type: String, default: '' } });
const emit = defineEmits(['update:modelValue', 'change']);
const selectedLabel = computed(() => props.options.find(opt => String(opt.value) === String(props.modelValue))?.label || '选择选项');
const items = computed(() => props.options.map(opt => ({ id: String(opt.value), label: opt.label, selected: String(opt.value) === String(props.modelValue) })));
function onChange(value) { emit('update:modelValue', value); emit('change', value); }
</script>
