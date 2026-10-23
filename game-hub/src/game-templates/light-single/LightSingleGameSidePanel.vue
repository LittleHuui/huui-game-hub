<template>
  <AppPageHeader class="light-single-header" :title="gameTitle" :meta="gameStatusText">
    <template #actions>
      <button v-if="fields.length" type="button" class="light-single-config-trigger" @click="configOpen = true">
        {{ fieldSummary || '配置' }}<AppIcon name="chevron" :size="14" />
      </button>
      <GameActionBar :actions="primaryActions" @action="$emit('action', $event)" />
      <AppMenu v-if="secondaryActions.length" label="更多操作" :items="secondaryActions" @select="$emit('action', $event)">
        <template #trigger><AppIcon name="more" /></template>
      </AppMenu>
    </template>
  </AppPageHeader>
  <AppModal :visible="configOpen" title="游戏配置" @close="configOpen = false">
    <div class="light-single-config">
      <GameControlField v-for="field in fields" :key="field.key" :field="field" @change="$emit('field-change', $event)">
        <slot :name="`field-${field.key}`" :field="field" />
      </GameControlField>
      <p class="light-single-config__description">{{ gameDescription }}</p>
      <slot name="title-extra" /><slot name="game-info-extra" />
      <dl v-if="infoStats.length" class="single-detail-list">
        <div v-for="stat in infoStats" :key="stat.key || stat.label"><dt>{{ stat.label }}</dt><dd>{{ stat.value }}</dd></div>
      </dl>
    </div>
    <template #footer><button type="button" class="gh-primary" @click="configOpen = false">完成</button></template>
  </AppModal>
</template>
<script setup>
import { computed, ref } from 'vue';
import AppModal from '../../components/AppModal.vue';
import AppPageHeader from '../../components/ui/AppPageHeader.vue';
import AppMenu from '../../components/ui/AppMenu.vue';
import AppIcon from '../../components/ui/AppIcon.vue';
import GameControlField from '../../components/game/controls/GameControlField.vue';
import GameActionBar from '../../components/game/controls/GameActionBar.vue';
const props = defineProps({
  gameTitle: { type: String, default: '' },
  gameDescription: { type: String, default: '' }, gameStatusText: { type: String, default: '' },
  infoStats: { type: Array, default: () => [] }, fields: { type: Array, default: () => [] },
  actionItems: { type: Array, default: () => [] }
});
defineEmits(['action', 'field-change']);
const configOpen = ref(false);
const primaryActions = computed(() => props.actionItems.filter((item) => item.visible !== false && !['secondary', 'danger'].includes(item.type)));
const secondaryActions = computed(() => props.actionItems.filter((item) => item.visible !== false && ['secondary', 'danger'].includes(item.type)).map((item) => ({ id: item.key, label: item.label, disabled: item.disabled, danger: item.type === 'danger' })));
const fieldSummary = computed(() => props.fields.map((field) => field.options?.find((option) => option.value === field.value)?.label).filter(Boolean).join(' · '));
</script>
