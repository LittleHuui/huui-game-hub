<template>
  <AppModal :visible="visible" title="登录 / 创建用户" @close="() => {}">
    <p v-if="platform.syncMessage" class="login-hint muted-small">{{ platform.syncMessage }}</p>
    <div class="modal-actions">
      <input
        v-model="loginUsername"
        placeholder="用户名"
        autocomplete="username"
        :disabled="busy"
        @keyup.enter="onLogin"
      />
      <button type="button" class="success" :disabled="busy" @click="onLogin">登录</button>
    </div>
    <p v-if="loginError" class="login-error">{{ loginError }}</p>

    <div class="modal-actions" style="margin-top: 16px">
      <input
        v-model="createUsername"
        placeholder="新用户名"
        autocomplete="off"
        :disabled="busy"
      />
      <input
        v-model="createNickname"
        placeholder="昵称"
        autocomplete="off"
        :disabled="busy"
        @keyup.enter="onCreate"
      />
      <button type="button" class="success" :disabled="busy" @click="onCreate">创建用户</button>
    </div>
    <p v-if="createError" class="login-error">{{ createError }}</p>
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

<style scoped>
.login-hint {
  margin: 0 0 12px;
  line-height: 1.5;
}

.login-error {
  margin: 8px 0 0;
  color: #fca5a5;
  font-size: 13px;
  line-height: 1.45;
}
</style>
