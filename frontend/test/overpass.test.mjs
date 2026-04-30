import assert from 'node:assert/strict'
import { mapElement, classifyKind } from '../src/lib/overpass.js'

const e = {
  type: 'node', id: 1, lat: 36.1, lon: -115.0,
  tags: { amenity: 'drinking_water', name: 'Public fountain' },
}
const m = mapElement(e)
assert.equal(m.kind, 'water')
assert.equal(m.lat, 36.1)
assert.equal(m.label, 'Public fountain')

assert.equal(classifyKind({ amenity: 'waste_disposal' }), 'trash')
assert.equal(classifyKind({ sanitary_dump_station: 'yes' }), 'dump')
assert.equal(classifyKind({ amenity: 'toilets' }), 'toilet')
assert.equal(classifyKind({ amenity: 'unknown' }), null)
assert.equal(classifyKind({}), null)

// element without classifiable tags → null
const eUnknown = { type: 'node', id: 2, lat: 36.0, lon: -115.0, tags: {} }
assert.equal(mapElement(eUnknown), null)

// element without lat → null
const eNoLat = { type: 'node', id: 3, tags: { amenity: 'drinking_water' } }
assert.equal(mapElement(eNoLat), null)

console.log('overpass: OK')
