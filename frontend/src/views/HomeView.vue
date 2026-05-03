<template>
  <main class="home">
    <header class="topbar">
      <span class="brand">
        <span class="brand-mark">●</span>
        <span class="brand-name">Voyage Map</span>
      </span>
      <!-- Issue stamp — pure flavour text, deliberately styled flatter than
           the brand mark so it doesn't read as a navigation link. -->
      <span class="brand-meta mono" aria-hidden="true">ISSUE №001 · FIELD GUIDE</span>
    </header>

    <TripSearchBar :trips="recents" @pick="onSearchPick" />

    <ResumeVoyagesPanel :recents="recents" @forget="forget" />

    <section class="form">
      <label class="eyebrow lbl" for="trip-title-field">Name your trip</label>
      <input
        id="trip-title-field"
        v-model="title"
        class="field title-field"
        placeholder="e.g. Vegas → SF road trip"
        maxlength="120"
      />

      <label class="eyebrow lbl">Where does the trip start?</label>
      <GeocoderSearch
        placeholder="Las Vegas · Mt. Fuji · 11° N 80° W…"
        :bias="homeBias"
        @pick="onPick"
      />
      <div class="origin-row">
        <button class="locate-link" type="button" @click="useMyLocation" :disabled="locating">
          ⌖ {{ locating ? 'Locating…' : 'Use my location' }}
        </button>
        <span v-if="picked" class="origin-chip" :title="picked.label">
          <span class="origin-chip-lbl mono">Starting from</span>
          <span class="origin-chip-val">{{ pickedShort }}</span>
          <button
            class="origin-chip-clear"
            type="button"
            title="Clear origin"
            @click="clearPicked"
          >×</button>
        </span>
      </div>
      <p v-if="locateError" class="error sm">{{ locateError }}</p>

      <Transition name="reveal">
        <div v-if="picked" ref="readyEl" class="ready-wrap">
          <div class="action-row">
            <label class="day1-toggle">
              <input type="checkbox" v-model="addDay1Stop" />
              <span>Add <strong>{{ pickedShort }}</strong> as a Day-1 stop ({{ todayLabel }})</span>
            </label>
            <button class="btn primary" :disabled="creating" @click="create">
              {{ creating ? 'Plotting…' : 'Begin journey →' }}
            </button>
          </div>
          <p v-if="error" class="error">{{ error }}</p>
        </div>
      </Transition>
    </section>

    <footer class="foot mono">
      EST. {{ year }} · CARTOGRAPHY BY YOU
    </footer>
  </main>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api.js'
import { getMyLocation } from '@/util.js'
import { recentMaps, rememberMap, forgetMap } from '@/lib/recents.js'
import { buildMapSlug } from '@/lib/slug.js'
import GeocoderSearch from '@/components/molecules/GeocoderSearch.vue'
import TripSearchBar from '@/components/molecules/TripSearchBar.vue'
import ResumeVoyagesPanel from '@/components/organisms/ResumeVoyagesPanel.vue'

const route = useRoute()
const router = useRouter()

// Personal-app convenience: when there's exactly one recent voyage, jump
// straight into it on '/'. Multi-voyage users still get the picker. The
// dock-back link "← Voyages" navigates here with ?home=1 so it overrides.
onMounted(() => {
  if (route.query.home != null) return
  const rs = recentMaps()
  if (rs.length === 1) {
    router.replace({ name: 'map', params: { slug: buildMapSlug(rs[0]) } })
  }
})
const year = new Date().getFullYear()

const picked = ref(null)
const title = ref('')
const creating = ref(false)
const error = ref('')
const locating = ref(false)
const locateError = ref('')
const recents = ref(recentMaps())
// Default-on: most trips start on the day they're created. The user can
// uncheck this if they're plotting a region map without a fixed Day 1.
const addDay1Stop = ref(true)

// First comma-segment is the human-friendly short name ("Las Vegas, Clark…"
// → "Las Vegas"). Used both in the chip and as the auto Day-1 stop title.
const pickedShort = computed(() => {
  if (!picked.value?.label) return ''
  return picked.value.label.split(',')[0].trim().slice(0, 120)
})

function todayIso() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
const todayLabel = computed(() =>
  new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
)

const homeBias = computed(() => {
  const r = recents.value[0]
  if (!r?.lastCenter) return null
  return { lat: r.lastCenter.lat, lng: r.lastCenter.lng, radiusKm: 1000 }
})

function forget(slug) {
  forgetMap(slug)
  recents.value = recentMaps()
}

function onSearchPick(trip) {
  router.push({ name: 'map', params: { slug: buildMapSlug(trip) } })
}

const readyEl = ref(null)

async function useMyLocation() {
  locating.value = true
  locateError.value = ''
  try {
    const loc = await getMyLocation()
    await onPick({ lat: loc.lat, lng: loc.lng, label: 'My current location' })
  } catch (e) {
    locateError.value = e.message
  } finally {
    locating.value = false
  }
}

async function onPick(r) {
  picked.value = r
  await nextTick()
  if (readyEl.value?.scrollIntoView) {
    readyEl.value.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function clearPicked() {
  picked.value = null
}

async function create() {
  if (!picked.value) return
  creating.value = true
  error.value = ''
  try {
    const m = await api.createMap({
      title: title.value.trim() || null,
      center_lat: picked.value.lat,
      center_lng: picked.value.lng,
      radius_m: 50000,
    })
    rememberMap(m.slug, m.title)

    // Auto Day-1 stop: create an itinerary day for today anchored at the
    // origin, and a `camp` pin attached to it. Failures here shouldn't block
    // the user from entering their map — log and continue.
    if (addDay1Stop.value) {
      try {
        const today = todayIso()
        const stopName = pickedShort.value || 'Day 1'
        const day = await api.addItineraryDay(m.slug, {
          date: today,
          label: stopName,
          lat: picked.value.lat,
          lng: picked.value.lng,
        })
        await api.addPoint(m.slug, {
          lat: picked.value.lat,
          lng: picked.value.lng,
          title: stopName,
          category: 'camp',
          itinerary_day_id: day?.id ?? null,
        })
      } catch (seedErr) {
        // Non-fatal: the map exists, user can add the pin manually.
        console.warn('Day-1 auto-stop failed:', seedErr)
      }
    }

    router.push({ name: 'map', params: { slug: buildMapSlug(m) } })
  } catch (e) {
    error.value = e.message || 'Could not chart your map.'
    creating.value = false
  }
}
</script>

<style scoped>
.home {
  min-height: 100%;
  max-width: 720px;
  margin: 0 auto;
  padding: 1.4rem clamp(1.2rem, 4vw, 3rem) 5rem;
  display: flex;
  flex-direction: column;
  gap: 1.6rem;
  position: relative;
}

/* Top bar -------------------------------------------------------- */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1.5px solid var(--ink);
  padding-bottom: 0.9rem;
}
.brand { display: inline-flex; align-items: center; gap: 0.55rem; }
.brand-mark { color: var(--vermillion); font-size: 1rem; line-height: 1; }
.brand-name {
  font-family: var(--display);
  font-size: 1.25rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.brand-meta {
  font-size: 0.66rem;
  letter-spacing: 0.22em;
  color: var(--ink-faded);
  cursor: default;
  user-select: none;
  font-style: italic;
  opacity: 0.85;
}

/* Form ----------------------------------------------------------- */
.form {
  display: grid;
  gap: 0.6rem;
  border: 1.5px solid var(--ink);
  border-radius: 6px;
  background: var(--paper);
  padding: 1.4rem 1.4rem 1.6rem;
  box-shadow: 6px 6px 0 var(--ink);
}
.lbl { color: var(--ink); font-weight: 700; }
.eyebrow.lbl { margin: 0; }
.form .eyebrow.lbl { margin-top: 0.3rem; }
.form .eyebrow.lbl:first-of-type { margin-top: 0; }

.title-field { width: 100%; font-size: 1.05rem; }

/* Origin chip ---------------------------------------------------- */
.origin-row {
  display: flex;
  gap: 0.7rem;
  align-items: center;
  flex-wrap: wrap;
  margin-top: -0.2rem;
}
.origin-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.25rem 0.45rem 0.25rem 0.6rem;
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  background: var(--cream);
  font-size: 0.85rem;
  max-width: 100%;
}
.origin-chip-lbl {
  font-size: 0.6rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.origin-chip-val {
  font-family: var(--display);
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 22ch;
}
.origin-chip-clear {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.1rem;
}
.origin-chip-clear:hover { color: var(--vermillion); }

/* Ready wrap (action bar — preview map removed in M2) ----------- */
.ready-wrap { display: grid; gap: 0.7rem; margin-top: 0.6rem; }
.action-row {
  display: flex;
  gap: 0.9rem;
  align-items: center;
  flex-wrap: wrap;
  justify-content: space-between;
  padding: 0.6rem 0.7rem;
  border: 1.5px dashed var(--ink);
  border-radius: 4px;
  background: var(--cream);
}
.day1-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.9rem;
  color: var(--ink-soft);
  cursor: pointer;
  flex: 1 1 240px;
  min-width: 0;
}
.day1-toggle input { accent-color: var(--vermillion); }
.day1-toggle strong { color: var(--ink); }
.btn.primary { font-weight: 700; }

.error { color: var(--vermillion-deep); font-weight: 500; margin: 0; }
.error.sm { font-size: 0.85rem; }

.locate-link {
  background: transparent;
  border: none;
  padding: 0.1rem 0;
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--vermillion);
  cursor: pointer;
}
.locate-link:hover { color: var(--vermillion-deep); }
.locate-link:disabled { color: var(--ink-faded); cursor: wait; }

/* Footer --------------------------------------------------------- */
.foot {
  text-align: center;
  font-size: 0.74rem;
  letter-spacing: 0.22em;
  color: var(--ink-faded);
  padding-top: 1rem;
  border-top: 1.5px solid var(--ink);
  margin-top: auto;
}

.reveal-enter-active { transition: opacity 280ms ease, transform 280ms ease; }
.reveal-enter-from { opacity: 0; transform: translateY(8px); }

@media (max-width: 720px) {
  .action-row { flex-direction: column; align-items: stretch; }
  .action-row .btn { width: 100%; }
}
</style>
