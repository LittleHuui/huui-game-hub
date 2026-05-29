import * as gameHubApi from '../api/gameHubApi.js';


/**
 * 远程数据源：仅封装 gameHubApi，不含 UI / store 逻辑。
 */
export const remoteRepository = {
  healthCheck: () => gameHubApi.healthCheck(),
  getBootContext: (payload) => gameHubApi.getBootContext(payload),
  syncCloudSave: (payload) => gameHubApi.syncCloudSave(payload),
  getGames: () => gameHubApi.getGames(),
  getGameConfig: (gameCode) => gameHubApi.getGameConfig(gameCode),
  getGameProps: (gameCode) => gameHubApi.getGameProps(gameCode),
  getGameRuleDefinition: (gameCode) => gameHubApi.getGameRuleDefinition(gameCode),
  getProps: (params) => gameHubApi.getProps(params),
  getLeaderboard: (params) => gameHubApi.getLeaderboard(params),
  login: (payload) => gameHubApi.login(payload),
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
