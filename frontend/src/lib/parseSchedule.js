// Parse a pasted itinerary into rows the importer can geocode + commit.
//
// Each non-empty, non-comment line is one day. Columns are split on tab,
// `;`, or `, ` (comma + space — single commas are kept inside fields like
// "Las Vegas, NV"). Recognised orders:
//
//   date                                     → empty placeholder day
//   date · name                              → day with a label, no location
//   date · name · location                   → day with explicit location
//   date · name · location · notes           → all four columns
//
// Date accepts:
//   YYYY-MM-DD                                (ISO)
//   DD/MM/YYYY  DD/MM        D MMM            (e.g. 9/5/2026, 9/5, "9 mai")
//   "samedi 9 mai"                            (weekday prefix is dropped)
//   "Sat May 9"                               (English short forms)
//
// When the year is missing it falls back to `defaultYear`. When the date
// can't be resolved, `error` is set and the row is excluded from import.

const FR_MONTHS = {
  jan: 0, janv: 0, janvier: 0,
  fev: 1, fév: 1, fevr: 1, fevrier: 1, février: 1,
  mar: 2, mars: 2,
  avr: 3, avril: 3,
  mai: 4,
  juin: 5,
  juil: 6, juillet: 6,
  aout: 7, août: 7,
  sep: 8, sept: 8, septembre: 8,
  oct: 9, octobre: 9,
  nov: 10, novembre: 10,
  dec: 11, déc: 11, decembre: 11, décembre: 11,
}
const EN_MONTHS = {
  jan: 0, january: 0,
  feb: 1, february: 1,
  mar: 2, march: 2,
  apr: 3, april: 3,
  may: 4,
  jun: 5, june: 5,
  jul: 6, july: 6,
  aug: 7, august: 7,
  sep: 8, sept: 8, september: 8,
  oct: 9, october: 9,
  nov: 10, november: 10,
  dec: 11, december: 11,
}
const MONTHS = { ...FR_MONTHS, ...EN_MONTHS }

const FR_WEEKDAYS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
const EN_WEEKDAYS = ['mon', 'tue', 'tues', 'wed', 'thu', 'thur', 'thurs', 'fri', 'sat', 'sun', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
const WEEKDAYS = new Set([...FR_WEEKDAYS, ...EN_WEEKDAYS])

function stripDiacritics(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '')
}

function isoToUTC(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

// Try every known date shape; return the ISO string or null.
export function parseDate(raw, defaultYear) {
  if (!raw) return null
  let s = raw.trim().toLowerCase()
  // Drop a leading weekday word: "samedi 9 mai", "Sat May 9".
  const firstWord = s.split(/\s+/)[0]
  if (WEEKDAYS.has(stripDiacritics(firstWord))) s = s.split(/\s+/).slice(1).join(' ')
  s = s.trim()

  // YYYY-MM-DD
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(s)
  if (m) return isoToUTC(+m[1], +m[2] - 1, +m[3])

  // D/M[/YYYY]
  m = /^(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?$/.exec(s)
  if (m) {
    const day = +m[1], mon = +m[2] - 1
    let year = m[3] ? +m[3] : defaultYear
    if (year < 100) year += 2000
    if (Number.isFinite(day) && mon >= 0 && mon <= 11) return isoToUTC(year, mon, day)
  }

  // "D mmm[ YYYY]" / "mmm D[, YYYY]"
  const tokens = s.replace(/[,]/g, ' ').split(/\s+/).filter(Boolean)
  let day = null, mon = null, year = null
  for (const tok of tokens) {
    const ascii = stripDiacritics(tok)
    if (/^\d+$/.test(tok)) {
      const n = +tok
      if (n >= 1900) year = n
      else if (day == null) day = n
      else year = n
    } else if (MONTHS[ascii] != null) {
      mon = MONTHS[ascii]
    }
  }
  if (day != null && mon != null) {
    return isoToUTC(year ?? defaultYear, mon, day)
  }

  return null
}

// Split a line on tabs, semicolons, or comma-followed-by-space.
function splitColumns(line) {
  const trimmed = line.trim()
  if (trimmed.includes('\t')) return trimmed.split('\t').map((x) => x.trim())
  if (trimmed.includes(';')) return trimmed.split(';').map((x) => x.trim())
  // ", " preserves "City, ST" inside a single field.
  return trimmed.split(/,\s+/).map((x) => x.trim())
}

export function parseScheduleText(text, { defaultYear } = {}) {
  const year = defaultYear || new Date().getFullYear()
  const lines = text.split(/\r?\n/)
  const rows = []
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]
    if (!raw.trim() || raw.trim().startsWith('#')) continue
    const cols = splitColumns(raw)
    const [dateRaw, name, location, notes] = [cols[0], cols[1], cols[2], cols.slice(3).join(', ')]
    const iso = parseDate(dateRaw || '', year)
    rows.push({
      lineNo: i + 1,
      raw,
      dateRaw: dateRaw || '',
      iso,
      name: name?.trim() || null,
      location: location?.trim() || null,
      notes: notes?.trim() || null,
      error: iso ? null : 'Could not read date',
      lat: null,
      lng: null,
      geocoded: false,
    })
  }
  return rows
}
