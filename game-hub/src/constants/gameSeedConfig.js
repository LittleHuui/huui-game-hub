/** 平台级游戏种子配置（本地 / 离线默认，在线失败时回退） */
export const GAME_SEED_CONFIG = {
  props: [
    {
      propCode: 'hint_card',
      propName: '提示卡',
      description: '提示所选格子是否为地雷',
      icon: '💡',
      basePrice: 500,
      enabled: true
    },
    {
      propCode: 'revive_card',
      propName: '复活卡',
      description: '踩雷后可复活一次，自动为踩中格插旗',
      icon: '💊',
      basePrice: 800,
      enabled: true
    },
    {
      propCode: 'match3_shuffle',
      propName: '洗牌',
      description: '重新排列当前棋盘，保留元素数量并确保仍可消除',
      icon: '🔀',
      basePrice: 800,
      enabled: true
    },
    {
      propCode: 'match3_bomb',
      propName: '炸弹',
      description: '选择一个格子，清除周围 3x3 区域',
      icon: '💥',
      basePrice: 1200,
      enabled: true
    }
  ],
  games: [
    {
      gameCode: 'minesweeper',
      gameName: '雷区突围',
      gameSubName: 'Mine Rush',
      supportOnline: false,
      enabled: true,
      sortNo: 1,
      config: {
        featureFlags: { leaderboard: true },
        ranking: {
          enabled: true,
          modes: {
            single: {
              primaryMetric: 'durationMs',
              orderDirection: 'asc',
              tieBreakers: [
                { metric: 'score', orderDirection: 'desc' },
                { metric: 'createdAt', orderDirection: 'asc' }
              ]
            }
          }
        }
      },
      difficulties: [
        {
          difficultyCode: 'easy',
          difficultyName: '初级',
          enabled: true,
          sortNo: 1,
          config: { rows: 9, cols: 9, mines: 10, winReward: 100, failRewardPerCorrectFlag: 3 }
        },
        {
          difficultyCode: 'medium',
          difficultyName: '中级',
          enabled: true,
          sortNo: 2,
          config: { rows: 16, cols: 16, mines: 40, winReward: 300, failRewardPerCorrectFlag: 3 }
        },
        {
          difficultyCode: 'hard',
          difficultyName: '高级',
          enabled: true,
          sortNo: 3,
          config: { rows: 16, cols: 30, mines: 100, winReward: 800, failRewardPerCorrectFlag: 3 }
        }
      ],
      clientConfigs: [],
      propRules: [
        {
          propCode: 'hint_card',
          sortNo: 1,
          price: 500,
          maxUsePerMatch: 5,
          triggerType: 'manual_select_cell',
          effectType: 'reveal_mine_hint',
          enabled: true,
          rule: {
            selectTarget: 'cell',
            resultType: 'isMine',
            consumeOnUse: true
          }
        },
        {
          propCode: 'revive_card',
          sortNo: 2,
          price: 800,
          maxUsePerMatch: 1,
          triggerType: 'on_mine_hit',
          effectType: 'revive_flag_mine',
          enabled: true,
          rule: {
            consumeOnUse: true,
            autoFlagMine: true
          }
        }
      ]
    },
    {
      gameCode: 'snake',
      gameName: '贪吃蛇',
      gameSubName: 'Snake Battle',
      supportOnline: true,
      enabled: true,
      sortNo: 3,
      config: {},
      difficulties: [],
      clientConfigs: [],
      propRules: []
    },
    {
      gameCode: 'tetris',
      gameName: '俄罗斯方块',
      gameSubName: 'Tetris Battle',
      supportOnline: true,
      enabled: true,
      sortNo: 4,
      config: {},
      difficulties: [],
      clientConfigs: [],
      propRules: []
    },
    {
      gameCode: 'match3',
      gameName: '幻彩碰撞',
      gameSubName: 'Color Crush',
      supportOnline: false,
      enabled: true,
      sortNo: 2,
      config: {
        featureFlags: {
          leaderboard: true,
          shop: true,
          inventory: true,
          offline: true,
          onlineBattle: false
        }
      },
      difficulties: [
        {
          difficultyCode: 'normal',
          difficultyName: '普通',
          enabled: true,
          sortNo: 1,
          config: {
            rows: 9,
            cols: 9,
            itemTypes: 6,
            allowInitialMatches: false,
            requireAtLeastOneMove: true,
            controlledRandom: {
              enabled: true,
              scoreStages: [
                { minScore: 0, friendliness: 0.35 },
                { minScore: 5000, friendliness: 0.22 },
                { minScore: 15000, friendliness: 0.12 },
                { minScore: 30000, friendliness: 0.05 }
              ]
            },
            scoreRules: {
              base: {
                3: 30,
                4: 60,
                5: 100
              },
              comboMultiplier: {
                1: 1,
                2: 1.5,
                3: 2,
                4: 3
              }
            },
            modes: {
              timed: {
                timeLimitSec: 180,
                propUseLimits: {
                  match3_shuffle: 2,
                  match3_bomb: 2
                }
              },
              endless: {
                timeLimitSec: 0,
                propUseLimits: {
                  match3_shuffle: 4,
                  match3_bomb: 3
                }
              }
            },
            settlement: {
              rewardRate: 0.01,
              minReward: 0
            },
            items: [
              { itemCode: 'red', color: '#E53935', icon: '' },
              { itemCode: 'blue', color: '#1E88E5', icon: '' },
              { itemCode: 'green', color: '#43A047', icon: '' },
              { itemCode: 'yellow', color: '#FDD835', icon: '' },
              { itemCode: 'purple', color: '#8E24AA', icon: '' },
              { itemCode: 'orange', color: '#FB8C00', icon: '' }
            ]
          }
        }
      ],
      clientConfigs: [
        {
          difficultyCode: 'normal',
          clientType: 'pc',
          enabled: true,
          config: {
            cellSize: 44,
            layoutMode: 'grid',
            animation: {
              swapMs: 180,
              removeMs: 220,
              dropMs: 260,
              chainDelayMs: 120
            }
          }
        }
      ],
      propRules: [
        {
          propCode: 'match3_shuffle',
          sortNo: 1,
          price: 800,
          maxUsePerMatch: 3,
          triggerType: 'manual',
          effectType: 'shuffle_board',
          enabled: true,
          rule: {
            keepItemCounts: true,
            allowMatchesAfterShuffle: false,
            requireAtLeastOneMove: true
          }
        },
        {
          propCode: 'match3_bomb',
          sortNo: 2,
          price: 1200,
          maxUsePerMatch: 3,
          triggerType: 'manual_select_cell',
          effectType: 'clear_area',
          enabled: true,
          rule: {
            radius: 1,
            shape: 'square',
            chainAfterUse: true
          }
        }
      ]
    }
  ]
};
