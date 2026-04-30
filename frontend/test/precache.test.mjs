import assert from 'node:assert/strict'
import { tilesForBbox, lonLatToTile } from '../src/lib/precache.js'

// Vegas at zoom 10
const t = lonLatToTile(36.17, -115.14, 10)
assert.equal(t.x, 184)
assert.equal(t.y, 401)

// Trip bbox at z6 should yield a small finite list
const list = tilesForBbox({ minLat: 33, maxLat: 39.5, minLng: -121, maxLng: -111.5 }, [6, 6])
assert.ok(list.length > 0 && list.length < 50, `z6 list size ${list.length}`)

// Bigger zoom = more tiles
const big = tilesForBbox({ minLat: 33, maxLat: 39.5, minLng: -121, maxLng: -111.5 }, [10, 10])
assert.ok(big.length > list.length)

console.log('precache: OK')
