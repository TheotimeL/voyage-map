import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import MapView from './views/MapView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/m/:slug', name: 'map', component: MapView, props: true },
  ],
})

export default router
