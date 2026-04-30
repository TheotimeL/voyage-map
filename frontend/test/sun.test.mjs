import assert from 'node:assert/strict'
import { sunInfo, formatCountdown } from '../src/lib/sun.js'

// Vegas, 1 May 2026 18:00 UTC ≈ 11:00 local (PDT)
const info = sunInfo(36.17, -115.14, new Date('2026-05-01T18:00:00Z'))
assert.ok(info.sunset instanceof Date, 'sunset is a Date')
assert.ok(info.civilEnd instanceof Date)
assert.ok(info.civilEnd > info.sunset, 'civil dusk after sunset')

assert.equal(formatCountdown(0), 'now')
assert.equal(formatCountdown(45 * 60_000), '45 min')
assert.equal(formatCountdown(75 * 60_000), '1h 15m')
assert.equal(formatCountdown(-30 * 60_000), '−30 min')

console.log('sun: OK')
