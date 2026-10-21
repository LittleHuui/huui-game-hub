import * as gameHubApi from '../api/gameHubApi.js';
import * as onlineAuthRepository from './onlineAuthRepository.js';


/**
 * 远程数据源：仅封装 gameHubApi，不含 UI / store 逻辑。
 */
export const remoteRepository = {
  readinessCheck: () => gameHubApi.readinessCheck(),
  getBootContext: (payload) => gameHubApi.getBootContext(payload),
  syncCloudSave: (payload, options) => gameHubApi.syncCloudSave(payload, options),
  getGames: () => gameHubApi.getGames(),
  getGameConfig: (gameCode) => gameHubApi.getGameConfig(gameCode),
  getGameProps: (gameCode) => gameHubApi.getGameProps(gameCode),
  getGameRuleDefinition: (gameCode) => gameHubApi.getGameRuleDefinition(gameCode),
  getProps: (params) => gameHubApi.getProps(params),
  getLeaderboard: (params) => gameHubApi.getLeaderboard(params),
  login: async (payload) => {
    const response = await gameHubApi.login(payload);
    const serverUserId =
      response?.user?.serverId ||
      response?.user?.userId ||
      response?.user?.id ||
      '';
    if (response?.accessToken && serverUserId) {
      onlineAuthRepository.saveToken(serverUserId, {
        accessToken: response.accessToken,
        expiresAt: response.expiresAt
      });
    }
    return response;
  },
  issueRealtimeTicket: () => gameHubApi.issueRealtimeTicket(),
  createUser: (payload) => gameHubApi.createUser(payload),
  getUser: (userId) => gameHubApi.getUser(userId),
  updateUserNickname: (userId, payload) => gameHubApi.updateUserNickname(userId, payload),
  bindUserDevice: (userId, payload) => gameHubApi.bindUserDevice(userId, payload),
  getUserSystemSetting: (userId) => gameHubApi.getUserSystemSetting(userId),
  updateUserSystemSetting: (userId, payload) => gameHubApi.updateUserSystemSetting(userId, payload),
  getUserGameSetting: (userId, gameCode) => gameHubApi.getUserGameSetting(userId, gameCode),
  updateUserGameSetting: (userId, gameCode, payload) => gameHubApi.updateUserGameSetting(userId, gameCode, payload),
  getWallet: (userId) => gameHubApi.getWallet(userId),
  getWalletLedgers: (userId, params) => gameHubApi.getWalletLedgers(userId, params),
  getInventory: (userId, params) => gameHubApi.getInventory(userId, params),
  getPropUsageRecords: (userId, params) => gameHubApi.getPropUsageRecords(userId, params),
  purchaseProp: (payload) => gameHubApi.purchaseProp(payload),
  getPurchases: (userId, params) => gameHubApi.getPurchases(userId, params),
  getMatches: (userId, params) => gameHubApi.getMatches(userId, params),
  getMatch: (matchId) => gameHubApi.getMatch(matchId)
};
