// frontend/test/elevation.test.mjs
import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('')
globalThis.DOMParser = dom.window.DOMParser

const { parseGPX } = await import('../src/util.js')
const { buildElevationSeries, elevationStats } = await import('../src/lib/elevation.js')

const sample = `<?xml version="1.0"?>
<gpx><trk><name>X</name><trkseg>
  <trkpt lat="36.17" lon="-115.14"><ele>610</ele></trkpt>
  <trkpt lat="36.18" lon="-115.13"><ele>650</ele></trkpt>
  <trkpt lat="36.19" lon="-115.12"><ele>700</ele></trkpt>
</trkseg></trk></gpx>`

const parsed = parseGPX(sample)
assert.equal(parsed.coords.length, 3)
assert.deepEqual(parsed.elevations, [610, 650, 700])

const series = buildElevationSeries(parsed.coords, parsed.elevations)
assert.equal(series.length, 3)
assert.equal(series[0].dist, 0)
assert.ok(series[2].dist > series[1].dist)
assert.equal(series[2].ele, 700)

const stats = elevationStats(series)
assert.equal(stats.gain, 90) // 40 + 50 m
assert.equal(stats.loss, 0)
assert.equal(stats.min, 610)
assert.equal(stats.max, 700)
assert.ok(stats.distanceKm > 0)

// Trkpt without <ele> → null in array
const sampleNoEle = `<?xml version="1.0"?>
<gpx><trk><trkseg>
  <trkpt lat="36.17" lon="-115.14"></trkpt>
  <trkpt lat="36.18" lon="-115.13"><ele>650</ele></trkpt>
</trkseg></trk></gpx>`
const parsed2 = parseGPX(sampleNoEle)
assert.deepEqual(parsed2.elevations, [null, 650])

// All-null elevations (OSM-derived trails imported via coordsToGPX) →
// hasElevation false + gain/loss null so callers can render "—" instead of
// a misleading "D+ 0 m".
const sampleAllNull = `<?xml version="1.0"?>
<gpx><trk><trkseg>
  <trkpt lat="36.17" lon="-115.14"></trkpt>
  <trkpt lat="36.18" lon="-115.13"></trkpt>
  <trkpt lat="36.19" lon="-115.12"></trkpt>
</trkseg></trk></gpx>`
const parsed3 = parseGPX(sampleAllNull)
const series3 = buildElevationSeries(parsed3.coords, parsed3.elevations)
const stats3 = elevationStats(series3)
assert.equal(stats3.hasElevation, false)
assert.equal(stats3.gain, null)
assert.equal(stats3.loss, null)
assert.ok(stats3.distanceKm > 0)

console.log('elevation: OK')
