import { ref, watch } from 'vue'

const KEY = 'voyage:theme'
const initial = localStorage.getItem(KEY)
  || (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')

export const theme = ref(initial)

function apply(t) {
  document.documentElement.dataset.theme = t
}

apply(theme.value)
watch(theme, (t) => {
  localStorage.setItem(KEY, t)
  apply(t)
})

export function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}
