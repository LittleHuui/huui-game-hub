/**
 * 按稳定难度编码继承默认值，保留远端的顺序和子集；未知编码不继承其他难度。
 * 玩法配置的合并策略由游戏提供。
 * @param {object[]} seedDefinitions
 * @param {object[]} definitions
 * @param {(seed: object, remote: object) => object} mergeConfig
 * @returns {object[]}
 */
export function mergeDifficultyDefinitions(seedDefinitions, definitions, mergeConfig) {
  const defaults = new Map(seedDefinitions.map((row) => [row.difficultyCode, row]));
  return definitions.map((row) => {
    const seed = defaults.get(row.difficultyCode) || {};
    return { ...seed, ...row, config: mergeConfig(seed.config, row.config) };
  });
}
