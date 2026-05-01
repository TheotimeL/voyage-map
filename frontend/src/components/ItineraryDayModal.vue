<template>
  <div class="scrim" @click.self="$emit('close')">
    <form class="paper modal" @submit.prevent="submit">
      <p class="eyebrow">Edit stop</p>

      <div class="date-row">
        <div class="date-cell">
          <label class="lbl">From</label>
          <input ref="dateInput" v-model="form.date" type="date" class="field" required />
        </div>
        <div class="date-cell">
          <label class="lbl">Until</label>
          <input v-model="form.end_date" type="date" class="field" :min="form.date" required />
        </div>
      </div>
      <p v-if="spanDays > 1" class="hint mono">{{ spanDays }} nights at this stop</p>

      <label class="lbl">Name</label>
      <input v-model="form.label" class="field" maxlength="200" placeholder="e.g. Hôtel Paradiso, Camp Joshua, BLM…" />

      <label class="lbl">Location</label>
      <GeocoderSearch
        :placeholder="hasCoord ? 'Change the location…' : 'Search a place — your existing pins show first'"
        :bias="bias"
        :local-candidates="existingPins"
        @pick="onPick"
      />
      <div v-if="hasCoord" class="coord-readout">
        <span class="coord mono">{{ formatLat(form.lat) }} · {{ formatLng(form.lng) }}</span>
        <button type="button" class="coord-clear" @click="clearLocation" title="Clear location">×</button>
      </div>
      <p class="hint mono">After saving, drag the day's pin on the map to fine-tune.</p>

      <label class="lbl">Notes</label>
      <textarea
        v-model="form.notes"
        class="field"
        maxlength="500"
        rows="3"
        placeholder="Hotel, plan, anything to remember"
      />

      <label class="lbl">Photos</label>
      <div class="photos">
        <ul v-if="photoUrls.length" class="photo-grid">
          <li v-for="(url, i) in photoUrls" :key="i" class="photo-cell">
            <img :src="url" alt="" />
            <button
              type="button"
              class="photo-rm"
              :title="`Remove photo ${i + 1}`"
              @click="removePhoto(i)"
            >×</button>
          </li>
        </ul>
        <label class="photo-add">
          <input
            type="file"
            accept="image/*"
            multiple
            class="hidden"
            @change="onPhotoPick"
          />
          <span>＋ Add photo{{ photoUrls.length ? 's' : '' }}</span>
        </label>
        <p v-if="photoError" class="error sm">{{ photoError }}</p>
      </div>

      <button v-if="hasCoord" type="button" class="btn directions" @click="onDirections">
        Directions →
      </button>

      <div class="row">
        <button type="button" class="btn btn-ghost" @click="$emit('close')">Cancel</button>
        <button type="submit" class="btn">Save</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { reactive, onMounted, onBeforeUnmount, useTemplateRef, computed, watch, ref } from 'vue'
import { formatLat, formatLng, openInMaps } from '@/util.js'
import GeocoderSearch from './GeocoderSearch.vue'

const props = defineProps({
  modelValue: { type: Object, required: true },
  bias: { type: Object, default: null },
  existingPins: { type: Array, default: () => [] },
})
const emit = defineEmits(['save', 'close'])

const form = reactive({
  date: props.modelValue.date,
  end_date: props.modelValue.end_date || props.modelValue.date,
  label: props.modelValue.label || '',
  notes: props.modelValue.notes || '',
  lat: props.modelValue.lat ?? null,
  lng: props.modelValue.lng ?? null,
})

// Photos: stored as a JSON array of base64 data-URLs in `photos`. Hydrate on
// open, edit in-place, serialize back on save. Per-image cap (~600 px wide,
// JPEG) keeps row sizes reasonable on a phone-first trip journal.
const photoUrls = ref([])
const photoError = ref('')
function hydratePhotos() {
  if (!props.modelValue.photos) { photoUrls.value = []; return }
  try {
    const parsed = JSON.parse(props.modelValue.photos)
    photoUrls.value = Array.isArray(parsed) ? parsed.filter((u) => typeof u === 'string') : []
  } catch {
    photoUrls.value = []
  }
}
hydratePhotos()

const MAX_PHOTOS = 12
const MAX_DIM = 1280
async function onPhotoPick(e) {
  photoError.value = ''
  const files = Array.from(e.target.files || []).filter((f) => /^image\//.test(f.type))
  e.target.value = ''
  for (const f of files) {
    if (photoUrls.value.length >= MAX_PHOTOS) {
      photoError.value = `Max ${MAX_PHOTOS} photos per stop — remove one to add more.`
      break
    }
    try {
      const url = await downscaleToDataUrl(f, MAX_DIM)
      photoUrls.value = [...photoUrls.value, url]
    } catch (err) {
      photoError.value = err.message || 'Could not read that image.'
    }
  }
}
function removePhoto(i) {
  photoUrls.value = photoUrls.value.filter((_, j) => j !== i)
}

// Downscale via canvas before base64-encoding. Without this a single 4K phone
// shot would balloon row size to many MB and slow every map load.
function downscaleToDataUrl(file, maxDim) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Could not read file'))
    reader.onload = () => {
      img.onerror = () => reject(new Error('Image decode failed'))
      img.onload = () => {
        const ratio = Math.min(1, maxDim / Math.max(img.width, img.height))
        const w = Math.round(img.width * ratio)
        const h = Math.round(img.height * ratio)
        const canvas = document.createElement('canvas')
        canvas.width = w
        canvas.height = h
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0, w, h)
        resolve(canvas.toDataURL('image/jpeg', 0.82))
      }
      img.src = reader.result
    }
    reader.readAsDataURL(file)
  })
}
const hasCoord = computed(() => form.lat != null && form.lng != null)
const spanDays = computed(() => {
  if (!form.date || !form.end_date) return 1
  return Math.max(1, Math.round((new Date(form.end_date) - new Date(form.date)) / 86400000) + 1)
})
// If the user shifts `From` past `Until`, snap `Until` along so the
// constraint never inverts mid-edit.
watch(() => form.date, (next) => {
  if (form.end_date && next > form.end_date) form.end_date = next
})

const dateInput = useTemplateRef('dateInput')
onMounted(() => dateInput.value?.focus())

function onEsc(e) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))

function onPick(result) {
  form.lat = result.lat
  form.lng = result.lng
  // If the user has not given a name yet, seed it from the picked place's
  // first part — keeps "name" decoupled from "location" but bootstraps it
  // for the common case.
  if (!form.label.trim() && result.label) {
    form.label = result.label.split(',')[0].trim().slice(0, 200)
  }
}

function clearLocation() {
  form.lat = null
  form.lng = null
}

function onDirections() {
  openInMaps(form.lat, form.lng, form.label.trim() || 'Day')
}

function submit() {
  emit('save', {
    date: form.date,
    end_date: form.end_date || form.date,
    label: form.label.trim() || null,
    notes: form.notes.trim() || null,
    lat: form.lat,
    lng: form.lng,
    // Send empty array as null so the row stays compact when the user clears
    // every photo. JSON.stringify handles escaping; consumers can JSON.parse
    // back on read (Itinerary chip + viewer).
    photos: photoUrls.value.length ? JSON.stringify(photoUrls.value) : null,
  })
}
</script>

<style scoped>
.modal {
  width: min(440px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  display: grid;
  gap: 0.7rem;
  padding: 1.4rem 1.5rem;
}
.date-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.7rem; }
.date-cell { display: grid; gap: 0.3rem; }
.lbl {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
  margin-top: 0.1rem;
}
.coord-readout {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.85rem;
  padding: 0.35rem 0.7rem;
  background: var(--cream);
  border-radius: 3px;
  border: 1px dashed var(--cream-edge);
}
.coord-clear {
  background: transparent;
  border: none;
  color: var(--ink-faded);
  font-size: 1rem;
  cursor: pointer;
  padding: 0 0.3rem;
}
.coord-clear:hover { color: var(--vermillion); }
.directions {
  width: 100%;
  margin-top: 0.3rem;
}
.row {
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
  margin-top: 0.5rem;
}
.hint { color: var(--ink-faded); font-size: 0.72rem; margin: 0; letter-spacing: 0.06em; }

.photos { display: grid; gap: 0.4rem; }
.photo-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 0.35rem;
}
.photo-cell {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 3px;
  overflow: hidden;
  border: 1px solid var(--cream-edge);
}
.photo-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.photo-rm {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 1.4rem;
  height: 1.4rem;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: var(--paper);
  border: none;
  font-size: 0.85rem;
  line-height: 1;
  cursor: pointer;
  display: grid;
  place-items: center;
}
.photo-rm:hover { background: var(--vermillion); }
.photo-add {
  display: inline-block;
  padding: 0.4rem 0.8rem;
  border: 1px dashed var(--cream-edge);
  border-radius: 3px;
  background: var(--cream);
  font-family: var(--mono);
  font-size: 0.74rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-soft);
  cursor: pointer;
  text-align: center;
  justify-self: start;
}
.photo-add:hover { color: var(--vermillion); border-color: var(--vermillion); }
.hidden { display: none; }
.error.sm { color: var(--vermillion-deep); font-size: 0.78rem; margin: 0; }
</style>
