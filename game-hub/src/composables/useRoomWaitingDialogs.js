import { ref } from 'vue';
import * as roomQueryService from '../services/roomQueryService.js';
import * as roomRealtimeService from '../services/roomRealtimeService.js';
import * as roomService from '../services/roomService.js';
import { estimateAiRemovalOnMaxPlayersChange } from '../utils/roomConfigFormUtils.js';
import * as toastService from '../services/toastService.js';

export function useRoomWaitingDialogs({ roomId, room, isRoomMember, context, actionBusy, errorMessage }) {
  const detailVisible = ref(false);
  const settingsVisible = ref(false);
  const settingsSubmitting = ref(false);
  const inviteDialogVisible = ref(false);
  const inviteUsers = ref([]);
  const inviteLoading = ref(false);
  const inviteSubmitting = ref(false);
  const inviteError = ref('');

  const removeMemberConfirmVisible = ref(false);
  const removeMemberTargetId = ref('');
  const removeMemberConfirmMessage = ref('确认移除该玩家？');

  const aiRemoveConfirmVisible = ref(false);
  const pendingSettingsPayload = ref(null);
  const pendingAiRemoveCount = ref(0);

  function resetDialogs() {
    detailVisible.value = false;
    settingsVisible.value = false;
    settingsSubmitting.value = false;
    inviteDialogVisible.value = false;
    inviteUsers.value = [];
    inviteLoading.value = false;
    inviteSubmitting.value = false;
    inviteError.value = '';
    removeMemberConfirmVisible.value = false;
    removeMemberTargetId.value = '';
    removeMemberConfirmMessage.value = '确认移除该玩家？';
    aiRemoveConfirmVisible.value = false;
    pendingSettingsPayload.value = null;
    pendingAiRemoveCount.value = 0;
  }
  function onOpenDetail() {
    detailVisible.value = true;
  }

  function onRemoveMemberRequest(targetPlayerId) {
    const normalizedTargetId = String(targetPlayerId || '').trim();
    if (!normalizedTargetId || !isRoomMember.value) {
      return;
    }
    const members = Array.isArray(room.value?.members) ? room.value.members : [];
    const target = members.find((item) => String(item?.playerId || '').trim() === normalizedTargetId);
    removeMemberTargetId.value = normalizedTargetId;
    removeMemberConfirmMessage.value = target?.isAi ? '确认移除该 AI？' : '确认移除该玩家？';
    removeMemberConfirmVisible.value = true;
  }

  function onCancelRemoveMember() {
    removeMemberConfirmVisible.value = false;
    removeMemberTargetId.value = '';
  }

  async function onConfirmRemoveMember() {
    if (actionBusy.value || settingsSubmitting.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const id = roomId.value;
    const normalizedTargetId = removeMemberTargetId.value;
    if (!id || !normalizedTargetId) {
      onCancelRemoveMember();
      return;
    }
    actionBusy.value = true;
    errorMessage.value = '';
    try {
      await roomService.removeRoomMember(id, normalizedTargetId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      await roomQueryService.loadRoomDetail(id, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      onCancelRemoveMember();
    } catch (err) {
      if (!operation.isCurrent()) return;
      toastService.push(err?.message || '移除玩家失败', 'error');
    } finally {
      if (operation.isCurrent()) actionBusy.value = false;
    }
  }

  async function onRoomSettingsSubmit(payload) {
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    if (payload?.error) {
      toastService.push(payload.error, 'warning');
      return;
    }
    const id = roomId.value;
    if (!id || !isRoomMember.value || !payload) {
      return;
    }
    const aiRemoveCount = estimateAiRemovalOnMaxPlayersChange(room.value, payload.maxPlayers);
    if (aiRemoveCount > 0) {
      pendingSettingsPayload.value = payload;
      pendingAiRemoveCount.value = aiRemoveCount;
      aiRemoveConfirmVisible.value = true;
      return;
    }
    await saveRoomSettings(payload);
    if (!operation.isCurrent()) return;
  }

  function onCancelAiRemoveConfirm() {
    aiRemoveConfirmVisible.value = false;
    pendingSettingsPayload.value = null;
    pendingAiRemoveCount.value = 0;
  }

  async function onConfirmAiRemoveAndSave() {
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const payload = pendingSettingsPayload.value;
    if (!payload) {
      onCancelAiRemoveConfirm();
      return;
    }
    await saveRoomSettings(payload);
    if (!operation.isCurrent()) return;
    onCancelAiRemoveConfirm();
  }

  async function saveRoomSettings(payload) {
    if (actionBusy.value || settingsSubmitting.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const id = roomId.value;
    if (!id || !isRoomMember.value) {
      return;
    }
    settingsSubmitting.value = true;
    try {
      await roomService.updateRoomConfig(id, payload, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      await roomQueryService.loadRoomDetail(id, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      settingsVisible.value = false;
    } catch (err) {
      if (!operation.isCurrent()) return;
      toastService.push(err?.message || '保存房间设置失败', 'error');
    } finally {
      if (operation.isCurrent()) settingsSubmitting.value = false;
    }
  }

  async function loadInviteUsers() {
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const id = roomId.value;
    if (!id) {
      return;
    }
    inviteLoading.value = true;
    inviteError.value = '';
    try {
      const users = await roomRealtimeService.loadInviteCandidates(id);
      if (!operation.isCurrent()) return;
      inviteUsers.value = users;
    } catch (err) {
      if (!operation.isCurrent()) return;
      inviteUsers.value = [];
      inviteError.value = err?.message || '加载在线用户失败';
    } finally {
      if (operation.isCurrent()) inviteLoading.value = false;
    }
  }

  function onInvite() {
    if (!room.value || !isRoomMember.value) {
      return;
    }
    inviteError.value = '';
    inviteDialogVisible.value = true;
    void loadInviteUsers();
  }

  async function onInviteUser(user) {
    if (inviteSubmitting.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const id = roomId.value;
    if (!id || !user?.serviceId) {
      return;
    }
    inviteSubmitting.value = true;
    try {
      roomRealtimeService.sendRoomInvite(id, {
        serviceId: user.serviceId,
        nickname: user.nickname
      });
      inviteDialogVisible.value = false;
    } catch (err) {
      if (!operation.isCurrent()) return;
      inviteError.value = err?.message || '邀请失败';
    } finally {
      if (operation.isCurrent()) inviteSubmitting.value = false;
    }
  }
  return {
    detailVisible,
    settingsVisible,
    settingsSubmitting,
    inviteDialogVisible,
    inviteUsers,
    inviteLoading,
    inviteSubmitting,
    inviteError,
    removeMemberConfirmVisible,
    removeMemberConfirmMessage,
    aiRemoveConfirmVisible,
    pendingAiRemoveCount,
    resetDialogs,
    onOpenDetail,
    onRemoveMemberRequest,
    onCancelRemoveMember,
    onConfirmRemoveMember,
    onRoomSettingsSubmit,
    onCancelAiRemoveConfirm,
    onConfirmAiRemoveAndSave,
    loadInviteUsers,
    onInvite,
    onInviteUser
  };
}
