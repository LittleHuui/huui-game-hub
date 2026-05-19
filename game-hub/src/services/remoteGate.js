import { usePlatformStore } from '../stores/platformStore.js';
import { useSettingStore } from '../stores/settingStore.js';

/**
 * 当前是否可从服务端拉取/同步数据。
 * @returns {boolean}
 */
export function canFetchRemote() {
  const settingStore = useSettingStore();
  if (settingStore.settings.repositoryMode === 'local') {
    return false;
  }
  const platform = usePlatformStore();
  return platform.networkMode === 'online' || platform.networkMode === 'degraded';
}
