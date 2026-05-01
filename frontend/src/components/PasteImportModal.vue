<template>
  <div class="scrim" @click.self="$emit('close')">
    <div class="paper paste-modal">
      <p class="eyebrow">Paste your schedule</p>
      <h3 class="paste-title">Bulk-import days from a spreadsheet</h3>

      <details class="paste-help" open>
        <summary>Format expected — click for examples</summary>
        <p class="help-lede mono">One day per line. Columns separated by <code>tab</code>, <code>;</code>, or <code>", "</code> (comma-space).</p>
        <p class="help-lede">
          Order: <code>date · name · location · notes</code>. Only the date is required.
          Location is geocoded for you (biased to the trip area). Notes are free text.
        </p>
        <p class="help-lede">Date forms accepted:</p>
        <ul class="help-list mono">
          <li><code>2026-05-09</code> — ISO</li>
          <li><code>9/5/2026</code> · <code>09/05</code> — D/M[/Y]</li>
          <li><code>9 mai</code> · <code>samedi 9 mai</code> — French (weekday optional)</li>
          <li><code>May 9</code> · <code>Sat May 9</code> — English short</li>
        </ul>
        <p class="help-lede">Lines starting with <code>#</code> are ignored. Year defaults to the field below.</p>
        <p class="help-lede">Sample:</p>
<pre class="help-sample mono">samedi 9 mai, Excalibur Hotel, Las Vegas
dimanche 10 mai, Excalibur Hotel, Las Vegas
lundi 11 mai, Cave Spring, Sedona AZ, ELECTRICITE
mardi 12 mai, Cave Spring, Sedona AZ
13/5, Mather Campground, Grand Canyon
14/5, BLM, Grand Canyon, free dispersed</pre>
      </details>

      <div class="row-inline">
        <label class="lbl">Default year</label>
        <input v-model.number="year" type="number" class="field year-field" :min="2020" :max="2050" />
      </div>

      <label class="replace-line">
        <input v-model="replaceMode" type="checkbox" />
        <span>Replace existing days <em class="hint mono">(wipes the current itinerary first — recommended when re-pasting from a spreadsheet)</em></span>
      </label>

      <label class="lbl">Paste below</label>
      <textarea
        v-model="text"
        class="field paste-area"
        rows="8"
        placeholder="samedi 9 mai, Excalibur Hotel, Las Vegas&#10;dimanche 10 mai, Excalibur Hotel, Las Vegas"
        @input="parsed = null"
      />

      <div class="paste-actions">
        <button type="button" class="btn btn-ghost" :disabled="busy" @click="onParse">
          {{ busy ? 'Geocoding…' : 'Preview' }}
        </button>
        <span class="parsed mono" v-if="parsed">
          {{ stats.ok }} row{{ stats.ok === 1 ? '' : 's' }} ready
          <template v-if="stats.warn">· {{ stats.warn }} without location</template>
          <template v-if="stats.bad">· {{ stats.bad }} skipped</template>
        </span>
      </div>

      <ol v-if="parsed" class="preview">
        <li
          v-for="row in parsed"
          :key="row.lineNo"
          :class="{ bad: !!row.error, warn: !row.error && (row.location && !row.geocoded) }"
        >
          <span class="p-date mono">{{ row.iso || row.dateRaw || '?' }}</span>
          <span class="p-name">{{ row.name || '—' }}</span>
          <span class="p-loc mono">
            <template v-if="row.geocoded">📍 {{ row.location || row.name }}</template>
            <template v-else-if="row.location">⚠ {{ row.location }} (no match)</template>
            <template v-else>—</template>
          </span>
          <span v-if="row.notes" class="p-notes">{{ row.notes }}</span>
          <span v-if="row.error" class="p-err mono">{{ row.error }}</span>
        </li>
      </ol>

      <p v-if="error" class="error sm">{{ error }}</p>

      <div class="row">
        <button type="button" class="btn btn-ghost" @click="$emit('close')">Cancel</button>
        <button
          type="button"
          class="btn"
          :disabled="!stats.ok"
          @click="onImport"
        >
          <template v-if="stats.ok">Import {{ stats.ok }} day{{ stats.ok === 1 ? '' : 's' }}</template>
          <template v-else>Preview to import</template>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { geocode } from '@/api.js'
import { parseScheduleText } from '@/lib/parseSchedule.js'

const props = defineProps({
  defaultYear: { type: Number, default: () => new Date().getFullYear() },
  bias: { type: Object, default: null },
})
const emit = defineEmits(['close', 'import'])

const text = ref('')
const year = ref(props.defaultYear)
const parsed = ref(null)
const busy = ref(false)
const error = ref('')
const replaceMode = ref(false)

const stats = computed(() => {
  const rows = parsed.value || []
  return {
    ok: rows.filter((r) => !r.error).length,
    warn: rows.filter((r) => !r.error && r.location && !r.geocoded).length,
    bad: rows.filter((r) => r.error).length,
  }
})

async function onParse() {
  error.value = ''
  busy.value = true
  try {
    const rows = parseScheduleText(text.value, { defaultYear: year.value })
    // Geocode rows with a `location` field, sequentially (Nominatim throttles)
    for (const row of rows) {
      if (row.error) continue
      if (!row.location) continue
      try {
        const results = await geocode(row.location, props.bias)
        if (results.length) {
          row.lat = results[0].lat
          row.lng = results[0].lng
          row.geocoded = true
        }
      } catch { /* leave row.geocoded = false */ }
    }
    parsed.value = rows
  } catch (e) {
    error.value = e.message || 'Could not parse schedule.'
  } finally {
    busy.value = false
  }
}

function onImport() {
  if (!parsed.value) return
  const rows = parsed.value
    .filter((r) => !r.error)
    .map((r) => ({
      date: r.iso,
      label: r.name || null,
      lat: r.geocoded ? r.lat : null,
      lng: r.geocoded ? r.lng : null,
      notes: r.notes || null,
    }))
  emit('import', { rows, replace: replaceMode.value })
}

function onEsc(e) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))
</script>

<style scoped>
.paste-modal {
  width: min(640px, 100%);
  max-height: 92vh;
  overflow-y: auto;
  display: grid;
  gap: 0.55rem;
  padding: 1.4rem 1.5rem;
}
.paste-title { margin: 0; font-size: 1.4rem; }
.paste-help {
  background: var(--cream);
  border: 1px dashed var(--cream-edge);
  border-radius: 4px;
  padding: 0.6rem 0.8rem;
  font-size: 0.88rem;
}
.paste-help summary {
  cursor: pointer;
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.paste-help[open] summary { color: var(--ink); margin-bottom: 0.5rem; }
.help-lede { color: var(--ink-soft); margin: 0.4rem 0; }
.help-list { margin: 0.2rem 0 0.5rem 1.1rem; padding: 0; }
.help-list li { margin-bottom: 0.15rem; }
.help-help-list code,
.help-lede code { background: var(--paper); padding: 0 4px; border-radius: 2px; font-size: 0.85em; }
.help-sample {
  background: var(--paper);
  border: 1px solid var(--cream-edge);
  padding: 0.55rem 0.7rem;
  font-size: 0.78rem;
  white-space: pre;
  overflow-x: auto;
  margin: 0.3rem 0 0;
  color: var(--ink-soft);
}
.lbl {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-faded);
}
.row-inline { display: flex; align-items: center; gap: 0.6rem; }
.year-field { width: 100px; }
.paste-area {
  font-family: var(--mono);
  font-size: 0.85rem;
  white-space: pre;
  overflow-x: auto;
  min-height: 9rem;
}
.paste-actions {
  display: flex;
  align-items: center;
  gap: 0.7rem;
}
.parsed {
  font-size: 0.78rem;
  color: var(--ink-faded);
  letter-spacing: 0.04em;
}
.preview {
  list-style: none;
  margin: 0.3rem 0 0;
  padding: 0;
  display: grid;
  gap: 0.2rem;
  max-height: 32vh;
  overflow-y: auto;
  border-top: 1px dashed var(--cream-edge);
  padding-top: 0.6rem;
}
.preview li {
  display: grid;
  grid-template-columns: 100px minmax(0, 1.5fr) minmax(0, 2fr) minmax(0, 1.5fr) auto;
  gap: 0.6rem;
  align-items: baseline;
  padding: 0.25rem 0.1rem;
  border-bottom: 1px dotted var(--cream-edge);
  font-size: 0.85rem;
}
.preview li.bad { background: rgba(232, 93, 60, 0.08); }
.preview li.warn { background: rgba(214, 169, 81, 0.10); }
.p-date { color: var(--ink-soft); font-size: 0.8rem; }
.p-name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; }
.p-loc { color: var(--ink-soft); font-size: 0.8rem; overflow: hidden; text-overflow: ellipsis; }
.p-notes { color: var(--ink-faded); font-size: 0.8rem; font-style: italic; overflow: hidden; text-overflow: ellipsis; }
.p-err { color: var(--vermillion-deep); font-size: 0.75rem; }
.row { display: flex; gap: 0.5rem; justify-content: flex-end; flex-wrap: wrap; margin-top: 0.4rem; }
.error.sm { font-size: 0.85rem; color: var(--vermillion-deep); margin: 0; }
.replace-line {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--ink-soft);
  cursor: pointer;
}
.replace-line input { margin-top: 0.2rem; }
.replace-line .hint { font-size: 0.72rem; color: var(--ink-faded); font-style: normal; }
</style>
