import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

/**
 * 勿在仓库根目录放置与前端路由路径同名的 `*.html`。
 * Vite 开发服会把 `/foo` 重写为根目录的 `foo.html`（若存在），从而绕过 SPA 的 index.html，
 * 导致例如 `/minesweeper` 误加载旧版单页而非 Vue Router。
 */
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173
  }
});
