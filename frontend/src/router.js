import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import MapView from './views/MapView.vue'
import ViewerView from './views/ViewerView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/m/:slug', name: 'map', component: MapView, props: true },
    // Read-only mirror — same data, no edit affordances. Sharing this URL
    // means recipients can browse the trip without accidentally clobbering
    // the host's plan. There's no auth, so it's "view-only by convention".
    { path: '/v/:slug', name: 'viewer', component: ViewerView, props: true },
  ],
})

export default router
