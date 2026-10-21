import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { initializeOnlineAuthContext } from './services/onlineAuthService.js';
import { initializeOnlineAuthenticationFailureService } from './services/onlineAuthenticationFailureService.js';
import './assets/app.css';

const app = createApp(App);
app.use(createPinia());
initializeOnlineAuthContext();
initializeOnlineAuthenticationFailureService();
app.use(router);
app.mount('#app');
