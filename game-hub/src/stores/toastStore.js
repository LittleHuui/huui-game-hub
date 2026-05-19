import { defineStore } from 'pinia';

export const useToastStore = defineStore('toast', {
  state: () => ({
    seq: 0,
    items: []
  }),
  actions: {
    /**
     * @param {string} message
     * @param {'info'|'success'|'warning'|'error'} level
     * @param {number} duration
     * @param {string|null} toastKind
     */
    push(message, level = 'info', duration = 3200, toastKind = null) {
      const id = ++this.seq;
      this.items.push({ id, level, message, toastKind });
      setTimeout(() => {
        this.items = this.items.filter((t) => t.id !== id);
      }, duration);
    }
  }
});
