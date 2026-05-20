import { defineStore } from 'pinia';

/**
 * @typedef {object} GameUser
 * @property {string} clientId
 * @property {string|null} serverId
 * @property {string} userId
 * @property {string} username
 * @property {string} nickname
 * @property {number} score
 * @property {number} totalScore
 * @property {boolean} autoRevive
 * @property {{ neighborHoverRing: boolean }} prefs
 * @property {number} createdAt
 * @property {number} updatedAt
 * @property {number|null} serverCreatedAt
 * @property {number|null} serverUpdatedAt
 * @property {number|null} syncedAt
 */

export const useUserStore = defineStore('user', {
  state: () => ({
    /** @type {{ currentUserId: string }} */
    auth: { currentUserId: '' },
    /** @type {GameUser[]} */
    users: []
  }),
  getters: {
    currentUser(state) {
      const id = state.auth.currentUserId;
      return (
        state.users.find((u) => u.userId === id) || {
          clientId: '',
          serverId: null,
          userId: '',
          username: 'unknown',
          nickname: '未知',
          score: 0,
          totalScore: 0,
          autoRevive: false,
          prefs: { neighborHoverRing: true },
          createdAt: 0,
          updatedAt: 0,
          serverCreatedAt: null,
          serverUpdatedAt: null,
          syncedAt: null
        }
      );
    }
  },
  actions: {
    /**
     * @param {GameUser[]} users
     * @param {{ currentUserId: string } | null} auth
     */
    hydrateUsersList(users, auth) {
      this.users = Array.isArray(users) ? [...users] : [];
      this.auth = auth && typeof auth === 'object' ? { ...auth } : { currentUserId: '' };
    },
    setCurrentUserId(id) {
      this.auth.currentUserId = id;
    },
    /**
     * @param {Omit<GameUser, 'score' | 'totalScore'> & Partial<Pick<GameUser, 'score' | 'totalScore'>>} partial
     */
    addUser(partial) {
      const now = Date.now();
      const user = {
        clientId: partial.clientId,
        serverId: partial.serverId ?? null,
        userId: partial.userId,
        username: partial.username,
        nickname: partial.nickname,
        score: partial.score ?? 0,
        totalScore: partial.totalScore ?? 0,
        autoRevive: !!partial.autoRevive,
        prefs: partial.prefs || { neighborHoverRing: true },
        createdAt: partial.createdAt ?? now,
        updatedAt: partial.updatedAt ?? now,
        serverCreatedAt: partial.serverCreatedAt ?? null,
        serverUpdatedAt: partial.serverUpdatedAt ?? null,
        syncedAt: partial.syncedAt ?? null
      };
      this.users.push(user);
    },
    patchNickname(userId, nickname) {
      const u = this.users.find((x) => x.userId === userId);
      if (u) {
        u.nickname = nickname;
        u.updatedAt = Date.now();
      }
    },
    patchUserScores(userId, score, totalScore) {
      const u = this.users.find((x) => x.userId === userId);
      if (u) {
        u.score = score;
        u.totalScore = totalScore;
        u.updatedAt = Date.now();
      }
    },
    setAutoRevive(userId, value) {
      const u = this.users.find((x) => x.userId === userId);
      if (u) {
        u.autoRevive = !!value;
        u.updatedAt = Date.now();
      }
    },
    setUserPrefs(userId, prefs) {
      const u = this.users.find((x) => x.userId === userId);
      if (u) {
        u.prefs = { ...u.prefs, ...prefs };
        u.updatedAt = Date.now();
      }
    }
  }
});
