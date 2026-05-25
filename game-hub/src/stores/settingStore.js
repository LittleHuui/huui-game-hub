import { defineStore } from 'pinia';
import { setRepositoryModeRuntime } from '../utils/repositoryModeRuntime.js';

export const useSettingStore = defineStore('setting', {
  state: () => ({
    settings: {
      storageVersion: 1,
      repositoryMode: 'auto'
    }
  }),
  actions: {
    replace(s) {
      this.settings =
        s && typeof s === 'object'
          ? {
              storageVersion: s.storageVersion ?? 1,
              repositoryMode: s.repositoryMode || 'auto'
            }
          : { storageVersion: 1, repositoryMode: 'auto' };
      setRepositoryModeRuntime(this.settings.repositoryMode);
    },
    setRepositoryMode(mode) {
      if (mode === 'auto' || mode === 'local' || mode === 'remote') {
        this.settings.repositoryMode = mode;
        setRepositoryModeRuntime(mode);
      }
    }
  }
});
