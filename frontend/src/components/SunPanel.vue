<template>
  <section v-if="info" class="sun-panel">
    <ul class="sun-rows">
      <li>
        <span class="lbl">Sunset</span>
        <span class="val">{{ formatTime(info.sunset) }}</span>
        <span class="cd mono" :class="{ urgent: cd.sunset < 60*60_000 && cd.sunset > 0 }">
          {{ formatCountdown(cd.sunset) }}
        </span>
      </li>
      <li>
        <span class="lbl">Civil dusk</span>
        <span class="val">{{ formatTime(info.civilEnd) }}</span>
        <span class="cd mono" :class="{ urgent: cd.civilEnd < 60*60_000 && cd.civilEnd > 0 }">
          {{ formatCountdown(cd.civilEnd) }}
        </span>
      </li>
      <li>
        <span class="lbl">Sunrise (next)</span>
        <span class="val">{{ formatTime(info.sunrise) }}</span>
      </li>
    </ul>
    <p v-if="locating" class="hint mono">Using map center — share location for your real position.</p>
    <button v-else-if="!gotPosition" class="locate-link" type="button" @click="locateMe">⌖ Use my location</button>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { sunInfo, formatTime, formatCountdown } from '@/lib/sun.js'
import { getMyLocation } from '@/util.js'

const props = defineProps({
  fallbackLat: { type: Number, required: true },
  fallbackLng: { type: Number, required: true },
})

const lat = ref(props.fallbackLat)
const lng = ref(props.fallbackLng)
const gotPosition = ref(false)
const locating = ref(false)
const tickHandle = ref(null)
const now = ref(new Date())

const info = computed(() => sunInfo(lat.value, lng.value, now.value))
const cd = computed(() => ({
  sunset: info.value.sunset.valueOf() - now.value.valueOf(),
  civilEnd: info.value.civilEnd.valueOf() - now.value.valueOf(),
}))

async function locateMe() {
  locating.value = true
  try {
    const loc = await getMyLocation()
    lat.value = loc.lat; lng.value = loc.lng
    gotPosition.value = true
  } catch { /* keep fallback */ }
  finally { locating.value = false }
}

onMounted(() => {
  tickHandle.value = setInterval(() => { now.value = new Date() }, 30_000)
})
onBeforeUnmount(() => { clearInterval(tickHandle.value) })
</script>

<style scoped>
.sun-panel { display: grid; gap: 0.35rem; }
.sun-rows { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.2rem; }
.sun-rows li {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: baseline;
  gap: 0.6rem;
  font-size: 0.85rem;
}
.lbl {
  font-family: var(--mono);
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.val { font-family: var(--display); font-size: 0.95rem; }
.cd { color: var(--ink-soft); }
.cd.urgent { color: var(--vermillion); font-weight: 700; }
.hint { font-size: 0.72rem; color: var(--ink-faded); margin: 0; letter-spacing: 0.06em; }
.locate-link {
  background: transparent;
  border: none;
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--vermillion);
  cursor: pointer;
  justify-self: start;
  padding: 0.1rem 0;
}
.locate-link:hover { color: var(--vermillion-deep); }
</style>
