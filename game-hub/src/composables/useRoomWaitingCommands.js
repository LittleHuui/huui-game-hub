import * as roomQueryService from '../services/roomQueryService.js';
import * as roomGameService from '../services/roomGameService.js';
import * as roomService from '../services/roomService.js';

export function useRoomWaitingCommands({ roomId, room, isRoomMember, context, actionBusy, rejoinBusy, errorMessage, shellRejoinOffered, ready, navigateLobby, navigatePlayRoom }) {
  async function onRejoinManagedRoom() {
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const id = roomId.value;
    if (!id || rejoinBusy.value) {
      return;
    }
    rejoinBusy.value = true;
    errorMessage.value = '';
    try {
      await roomService.rejoinManagedRoom(id, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      shellRejoinOffered.value = false;
      await roomQueryService.loadRoomDetail(id, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      ready.value = true;
      const status = String(room.value?.status || '').trim();
      if (status === 'playing') {
        await navigatePlayRoom();
        if (!operation.isCurrent()) return;
      }
    } catch (err) {
      if (!operation.isCurrent()) return;
      errorMessage.value = err?.message || '重新加入失败';
    } finally {
      if (operation.isCurrent()) rejoinBusy.value = false;
    }
  }

  async function onBackToLobbyFromShell() {
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    await navigateLobby();
    if (!operation.isCurrent()) return;
  }

  async function onLeaveRoom() {
    if (actionBusy.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const id = roomId.value;
    if (!id) {
      await navigateLobby();
      if (!operation.isCurrent()) return;
      return;
    }
    actionBusy.value = true;
    errorMessage.value = '';
    try {
      await roomService.leaveRoom(id, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      await navigateLobby();
      if (!operation.isCurrent()) return;
    } catch (err) {
      if (!operation.isCurrent()) return;
      errorMessage.value = err?.message || '离开房间失败';
    } finally {
      if (operation.isCurrent()) actionBusy.value = false;
    }
  }

  async function onAddAi() {
    if (actionBusy.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const id = roomId.value;
    if (!id || !isRoomMember.value) {
      return;
    }
    actionBusy.value = true;
    errorMessage.value = '';
    try {
      await roomService.addRoomAi(id, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      await roomQueryService.loadRoomDetail(id, { signal: operation.signal });
      if (!operation.isCurrent()) return;
    } catch (err) {
      if (!operation.isCurrent()) return;
      errorMessage.value = err?.message || '添加 AI 失败';
    } finally {
      if (operation.isCurrent()) actionBusy.value = false;
    }
  }

  async function onStartGame() {
    if (actionBusy.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const id = roomId.value;
    if (!id || !isRoomMember.value) {
      return;
    }
    actionBusy.value = true;
    errorMessage.value = '';
    try {
      await roomGameService.startRoomGame(id, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      await roomQueryService.loadRoomDetail(id, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      const status = String(room.value?.status || '').trim();
      if (status === 'playing') {
        await navigatePlayRoom();
        if (!operation.isCurrent()) return;
      }
    } catch (err) {
      if (!operation.isCurrent()) return;
      errorMessage.value = err?.message || '开始游戏失败';
    } finally {
      if (operation.isCurrent()) actionBusy.value = false;
    }
  }
  return {
    onRejoinManagedRoom,
    onBackToLobbyFromShell,
    onLeaveRoom,
    onAddAi,
    onStartGame
  };
}
