let repositoryMode = 'auto';

/**
 * 写入当前数据仓库运行模式。
 * @param {'auto'|'local'|'remote'} mode
 */
export function setRepositoryModeRuntime(mode) {
  if (mode === 'auto' || mode === 'local' || mode === 'remote') {
    repositoryMode = mode;
  }
}

/**
 * 读取当前数据仓库运行模式。
 * @returns {'auto'|'local'|'remote'}
 */
export function getRepositoryModeRuntime() {
  return repositoryMode;
}
