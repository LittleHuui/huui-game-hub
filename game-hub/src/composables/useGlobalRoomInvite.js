import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useRoomStore } from '../stores/roomStore.js';
import * as roomService from '../services/roomService.js';
import * as roomQueryService from '../services/roomQueryService.js';
import { getRoomMembershipScope } from '../services/roomAccessService.js';
import { ensureGlobalRealtimeHandlers } from '../services/gameHubRealtimeService.js';
import * as toastService from '../services/toastService.js';
import { resolveGamePlayRoute } from '../games/gameModuleRegistry.js';
import { useAsyncContext } from './useAsyncContext.js';

/**
 * 全局邀请交互；查询共享成员归属，按当前身份生命周期执行加入与导航。
 * @returns {object} 邀请展示状态与明确的接受、拒绝入口。
 */
export function useGlobalRoomInvite() {
  ensureGlobalRealtimeHandlers();
  const router = useRouter();
  const context = useAsyncContext();
  const roomStore = useRoomStore();
  const { pendingInvite } = storeToRefs(roomStore);
  const inviteActionSubmitting = ref(false);
  const inviteActionError = ref('');
  watch(getRoomMembershipScope, () => {
    context.reset();
    roomQueryService.synchronizeActiveRoomScope();
    inviteActionSubmitting.value = false;
    inviteActionError.value = '';
  }, { immediate: true, flush: 'sync' });

  /**
   * 关闭邀请弹窗。
   */
  function rejectInvite() {
    roomStore.clearPendingInvite();
    inviteActionSubmitting.value = false;
    inviteActionError.value = '';
  }

  /**
   * 接受邀请前重查成员归属，详情缓存不能阻止真实空闲用户加入。
   * @returns {Promise<void>} 服务完成成员对账；切换身份或卸载后不再更新 UI 或导航。
   */
  async function acceptInvite() {
    if (inviteActionSubmitting.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const invite = pendingInvite.value;
    const roomId = String(invite?.roomId || '').trim();
    if (!roomId) {
      rejectInvite();
      return;
    }
    inviteActionSubmitting.value = true;
    inviteActionError.value = '';
    try {
      const activeRoom = await roomQueryService.loadMyActiveRoom({ signal: operation.signal });
      if (!operation.isCurrent()) return;
      if (activeRoom?.roomId && activeRoom.roomId !== roomId) {
        toastService.push('请先离开当前房间后再接受邀请', 'warning');
        return;
      }
      const room = await roomService.joinRoom(roomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      roomStore.clearPendingInvite();
      const gameCode = String(room.gameCode || invite?.gameCode || '').trim();
      if (!gameCode) {
        throw new Error('房间缺少 gameCode');
      }
      if (room.status === 'playing') {
        const playRoute = resolveGamePlayRoute(gameCode, room.roomId);
        if (!playRoute) {
          throw new Error('当前游戏不支持在线对战');
        }
        await router.push(playRoute);
        return;
      }
      await router.push({
        name: 'online-room-waiting',
        params: { gameCode, roomId: room.roomId }
      });
    } catch (err) {
      if (operation.isCurrent() && err?.name !== 'AbortError') inviteActionError.value = err?.message || '加入房间失败';
    } finally {
      if (operation.isCurrent()) inviteActionSubmitting.value = false;
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
