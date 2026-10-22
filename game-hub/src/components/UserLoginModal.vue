<template>
  <AppModal :visible="visible" title="欢迎来到 Game Hub" :closable="false" :mask-closable="false">
    <p v-if="platform.syncMessage" class="login-hint muted-small">{{ platform.syncMessage }}</p>
    <div class="login-tabs"><button type="button" :class="{ 'is-active': view === 'login' }" @click="view = 'login'">登录</button><button type="button" :class="{ 'is-active': view === 'create' }" @click="view = 'create'">创建用户</button></div>
    <form v-if="view === 'login'" class="login-form" @submit.prevent="onLogin"><label>用户名<input v-model="loginUsername" autocomplete="username" placeholder="输入用户名" :disabled="busy" /></label><button type="submit" class="success" :disabled="busy">{{ busy ? '正在登录…' : '登录' }}</button><p v-if="loginError" class="login-error" role="alert">{{ loginError }}</p></form>
    <form v-else class="login-form" @submit.prevent="onCreate"><label>用户名<input v-model="createUsername" autocomplete="off" placeholder="新用户名" :disabled="busy" /></label><label>昵称<input v-model="createNickname" autocomplete="off" placeholder="游戏中显示的名字" :disabled="busy" /></label><button type="submit" class="success" :disabled="busy">{{ busy ? '正在创建…' : '创建用户' }}</button><p v-if="createError" class="login-error" role="alert">{{ createError }}</p></form>
  </AppModal>
</template>

<script setup>
import { ref } from 'vue';
import AppModal from './AppModal.vue';
import { usePlatformStore } from '../stores/platformStore.js';
import * as userService from '../services/userService.js';

defineProps({
  visible: { type: Boolean, default: false }
});

const emit = defineEmits(['success']);

const platform = usePlatformStore();

const loginUsername = ref('');
const createUsername = ref('');
const createNickname = ref('');
const loginError = ref('');
const createError = ref('');
const busy = ref(false);
const view = ref('login');

/**
 * 提交登录。
 */
async function onLogin() {
  if (busy.value) {
    return;
  }
  loginError.value = '';
  busy.value = true;
  try {
    const res = await userService.login(loginUsername.value);
    if (res.success) {
      emit('success');
    } else {
      loginError.value = res.message || '登录失败';
    }
  } finally {
    busy.value = false;
  }
}

/**
 * 提交创建用户。
 */
async function onCreate() {
  if (busy.value) {
    return;
  }
  createError.value = '';
  busy.value = true;
  try {
    const res = await userService.createAndLogin(createUsername.value, createNickname.value);
    if (res.success) {
      emit('success');
    } else {
      createError.value = res.message || '创建用户失败';
    }
  } finally {
    busy.value = false;
  }
}
</script>
