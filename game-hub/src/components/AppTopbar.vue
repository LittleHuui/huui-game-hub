<template>
  <header class="site-topbar">
    <div class="site-topbar-inner">
      <div class="site-brand">
        <img class="site-logo-mark" src="/favicon.svg" alt="" />
        <div class="site-brand-text">
          <span class="site-title gh-site-title">Game Hub</span>
        </div>
      </div>
      <div v-if="hasGamesSlot" class="site-topbar-games">
        <slot name="games" />
      </div>
      <div class="site-user-bar">
        <div class="site-user-meta">
          <input
            v-if="editingNickname"
            ref="nickInput"
            v-model="nicknameDraft"
            class="nickname-input site-nickname-input"
            @blur="saveNickname"
            @keyup.enter="onEnterBlur"
          />
          <button
            v-else
            type="button"
            class="nickname-text site-nickname-text"
            :class="{ 'is-locked': lockNickname }"
            :title="lockNickname ? '对局进行中不可修改昵称' : '点击修改昵称'"
            @click="startNicknameEdit"
          >
            {{ user.nickname }}
          </button>
        </div>
        <div class="site-user-trail">
          <slot name="menu" />
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, watch, nextTick, useSlots, computed } from 'vue';

const props = defineProps({
  user: { type: Object, required: true },
  lockNickname: { type: Boolean, default: false }
});

const emit = defineEmits(['update-nickname']);

const editingNickname = ref(false);
const nicknameDraft = ref('');
const nickInput = ref(null);
const slots = useSlots();
const hasGamesSlot = computed(() => !!slots.games);

function startNicknameEdit() {
  if (props.lockNickname) {
    return;
  }
  nicknameDraft.value = props.user.nickname;
  editingNickname.value = true;
  nextTick(() => nickInput.value?.focus());
}

function saveNickname() {
  const nickname = nicknameDraft.value.trim();
  if (!nickname) {
    nicknameDraft.value = props.user.nickname;
    editingNickname.value = false;
    return;
  }
  emit('update-nickname', nickname);
  editingNickname.value = false;
}

function onEnterBlur(e) {
  e.target.blur();
}

watch(
  () => props.user.nickname,
  () => {
    if (!editingNickname.value) {
      nicknameDraft.value = props.user.nickname;
    }
  }
);
</script>
