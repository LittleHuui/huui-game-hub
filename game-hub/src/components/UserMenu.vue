<template>
  <AppMenu class="account-menu" label="账户菜单" title="我的账户" :items="items" @select="emit('open-modal', $event)">
    <template #trigger><span class="account-menu-avatar">{{ (user.nickname || user.username || '我').slice(0, 1) }}</span></template>
    <template #header><div class="account-menu-summary"><strong>{{ user.nickname }}</strong><span>{{ user.username }}</span><span>积分 {{ user.score || 0 }} · 总积分 {{ user.totalScore || 0 }}</span></div></template>
  </AppMenu>
</template>
<script setup>
import { computed } from 'vue';
import AppMenu from './ui/AppMenu.vue';
const props = defineProps({ user: { type: Object, required: true }, disableSwitch: { type: Boolean, default: false } });
const emit = defineEmits(['open-modal']);
const items = computed(() => [
  { id: 'nickname', label: '修改昵称', icon: 'edit', disabled: props.disableSwitch },
  { id: 'ledger', label: '积分流水', icon: 'coins' },
  { id: 'history', label: '历史对局', icon: 'clock' },
  { id: 'propUsage', label: '道具使用记录', icon: 'backpack' },
  { id: 'purchase', label: '购买记录', icon: 'receipt' },
  { id: 'settings', label: '显示与数据设置', icon: 'settings' },
  { id: 'divider', type: 'separator' },
  { id: 'user', label: '切换或创建用户', icon: 'user', disabled: props.disableSwitch }
]);
</script>
