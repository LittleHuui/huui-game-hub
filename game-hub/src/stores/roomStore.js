import { defineStore } from 'pinia';

export const useRoomStore = defineStore('room', {
  state: () => ({
    /** @type {string} */
    activeGameCode: '',
    /** @type {object[]} */
    rooms: [],
    roomsLoading: false,
    roomsError: '',
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
     * 按 version 合并房间详情；未推进时忽略。
     * @param {object} room
     * @returns {boolean} 是否已写入
     */
    applyRoomIfNewer(room) {
      if (!room || typeof room !== 'object') {
        return false;
      }
      const incomingVersion = Number(room.version) || 0;
      const current = this.currentRoom;
      if (current && current.roomId === room.roomId && incomingVersion <= (Number(current.version) || 0)) {
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
