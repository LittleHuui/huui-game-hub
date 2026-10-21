import { defineStore } from 'pinia';

export const useRoomStore = defineStore('room', {
  state: () => ({
    /** @type {string} */
    activeGameCode: '',
    /** @type {object[]} */
    rooms: [],
    roomsLoading: false,
    roomsError: '',
    /** 服务端成员归属查询快照，不能由房间详情推断。 */
    activeRoom: null,
    activeRoomError: '',
    activeRoomScope: '',
    activeRoomQueryStatus: 'idle',
    /** @type {object|null} */
    currentRoom: null,
    currentRoomLoading: false,
    currentRoomError: '',
    /** @type {object|null} */
    roomRule: null,
    /** @type {object|null} */
    roomConfigSchema: null,
    /** @type {object|null} */
    pendingInvite: null
  }),
  actions: {
    /**
     * 切换查询快照上下文，仅在身份、服务或数据模式变化时清空。
     * @param {string} scope 当前成员查询上下文。
     * @returns {void} 不修改服务端成员资格。
     */
    setActiveRoomScope(scope) {
      this.activeRoomScope = scope;
      this.activeRoom = null;
      this.activeRoomError = '';
      this.activeRoomQueryStatus = 'idle';
    },
    /**
     * 保存服务端查询的当前成员房间。
     * @param {object|null} room 服务端查询结果。
     * @returns {void} 只更新快照，不写入详情或对局。
     */
    setActiveRoom(room) {
      this.activeRoom = room;
      this.activeRoomError = '';
      this.activeRoomQueryStatus = 'ready';
    },
    /**
     * 记录成员查询错误，保留最后一次已知房间。
     * @param {string} message 查询错误。
     * @returns {void}
     */
    setActiveRoomError(message) {
      this.activeRoomError = message;
      this.activeRoomQueryStatus = 'error';
    },
    /**
     * 标记归属查询进度；取消或命令开始后，旧快照不能被当作本次对账结果。
     * @param {'idle'|'loading'} status 查询进度。
     * @returns {void} 保留已有快照与错误。
     */
    setActiveRoomQueryStatus(status) {
      this.activeRoomQueryStatus = status;
    },
    setActiveGameCode(gameCode) {
      this.activeGameCode = gameCode || '';
    },
    setRooms(rooms) {
      this.rooms = Array.isArray(rooms) ? rooms : [];
    },
    setRoomsLoading(loading) {
      this.roomsLoading = Boolean(loading);
    },
    setRoomsError(message) {
      this.roomsError = message || '';
    },
    setCurrentRoom(room) {
      this.currentRoom = room && typeof room === 'object' ? room : null;
    },
    setCurrentRoomLoading(loading) {
      this.currentRoomLoading = Boolean(loading);
    },
    setCurrentRoomError(message) {
      this.currentRoomError = message || '';
    },
    setRoomRuleContext(context) {
      const payload = context && typeof context === 'object' ? context : {};
      this.roomRule = payload.roomRule && typeof payload.roomRule === 'object' ? payload.roomRule : null;
      this.roomConfigSchema = Array.isArray(payload.roomConfigSchema)
        ? payload.roomConfigSchema
        : null;
    },
    clearRooms() {
      this.rooms = [];
      this.roomsError = '';
    },
    clearCurrentRoom() {
      this.currentRoom = null;
      this.currentRoomError = '';
    },
    setPendingInvite(invite) {
      this.pendingInvite = invite && typeof invite === 'object' ? invite : null;
    },
    clearPendingInvite() {
      this.pendingInvite = null;
    },
    /**
     * 按 roomVersion 合并房间详情；未推进时忽略。
     * @param {object} room
     * @returns {boolean} 是否已写入
     */
    applyRoomIfNewer(room) {
      if (!room || typeof room !== 'object') {
        return false;
      }
      const incomingVersion = Number(room.roomVersion) || 0;
      const current = this.currentRoom;
      if (current && current.roomId === room.roomId && incomingVersion <= (Number(current.roomVersion) || 0)) {
        return false;
      }
      if (!current || current.roomId === room.roomId) {
        this.setCurrentRoom(room);
      }
      if (this.activeGameCode && room.gameCode === this.activeGameCode) {
        const nextRooms = this.rooms.map((item) =>
          item.roomId === room.roomId
            ? {
                ...item,
                roomName: room.roomName,
                memberCount: room.memberCount,
                maxPlayers: room.maxPlayers,
                aiCount: room.aiCount,
                status: room.status
              }
            : item
        );
        this.setRooms(nextRooms);
      }
      return true;
    }
  }
});
