import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useRoomStore } from '../stores/roomStore.js';
import * as roomService from '../services/roomService.js';
import { ensureGlobalRealtimeHandlers } from '../services/gameHubRealtimeService.js';
import * as toastService from '../services/toastService.js';

/**
 * 全局房间邀请弹窗：同意/拒绝与路由跳转。
 */
export function useGlobalRoomInvite() {
  ensureGlobalRealtimeHandlers();
  const router = useRouter();
  const roomStore = useRoomStore();
  const { pendingInvite, currentRoom } = storeToRefs(roomStore);
  const inviteActionSubmitting = ref(false);
  const inviteActionError = ref('');

  /**
   * 关闭邀请弹窗。
   */
  function rejectInvite() {
    roomStore.clearPendingInvite();
    inviteActionSubmitting.value = false;
    inviteActionError.value = '';
  }

  /**
   * 同意邀请并加入房间。
   */
  async function acceptInvite() {
    const invite = pendingInvite.value;
    const roomId = String(invite?.roomId || '').trim();
    if (!roomId) {
      rejectInvite();
      return;
    }
    const activeRoomId = String(currentRoom.value?.roomId || '').trim();
    if (activeRoomId && activeRoomId !== roomId) {
      toastService.push('请先离开当前房间后再接受邀请', 'warning');
      return;
    }
    inviteActionSubmitting.value = true;
    inviteActionError.value = '';
    try {
      const room = await roomService.joinRoom(roomId);
      roomStore.clearPendingInvite();
      const gameCode = String(room.gameCode || invite?.gameCode || '').trim();
      if (!gameCode) {
        throw new Error('房间缺少 gameCode');
      }
      if (room.status === 'playing') {
        await router.push({
          name: 'online-play-entry',
          params: { gameCode, roomId: room.roomId }
        });
        return;
      }
      await router.push({
        name: 'online-room-waiting',
        params: { gameCode, roomId: room.roomId }
      });
    } catch (err) {
      inviteActionError.value = err?.message || '加入房间失败';
    } finally {
      inviteActionSubmitting.value = false;
    }
  }

  return {
    pendingInvite,
    inviteActionSubmitting,
    inviteActionError,
    rejectInvite,
    acceptInvite
  };
}
