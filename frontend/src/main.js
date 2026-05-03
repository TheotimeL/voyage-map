import { createApp } from 'vue'
import { registerSW } from 'virtual:pwa-register'
import App from './App.vue'
import router from './router'

import 'leaflet/dist/leaflet.css'
import './styles/vintage.css'

createApp(App).use(router).mount('#app')

// Service worker — silently auto-updates. The user always gets the latest on reload.
registerSW({ immediate: true })
