// frontend/src/lib/elevation.js
const R = 6371000

function haversine([lat1, lng1], [lat2, lng2]) {
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

export function buildElevationSeries(coords, elevations, targetPoints = 200) {
  if (!coords.length) return []
  const series = []
  let dist = 0
  for (let i = 0; i < coords.length; i++) {
    if (i > 0) dist += haversine(coords[i - 1], coords[i])
    series.push({
      dist,
      ele: elevations?.[i] ?? null,
      coord: coords[i],
    })
  }
  if (series.length <= targetPoints) return series
  const step = series.length / targetPoints
  const out = []
  for (let i = 0; i < targetPoints; i++) out.push(series[Math.floor(i * step)])
  out.push(series[series.length - 1])
  return out
}

export function elevationStats(series) {
  let gain = 0, loss = 0, min = Infinity, max = -Infinity
  for (let i = 0; i < series.length; i++) {
    const e = series[i].ele
    if (e == null) continue
    if (e < min) min = e
    if (e > max) max = e
    if (i > 0 && series[i - 1].ele != null) {
      const d = e - series[i - 1].ele
      if (d > 0) gain += d
      else loss += -d
    }
  }
  return {
    gain: Math.round(gain),
    loss: Math.round(loss),
    min: Number.isFinite(min) ? Math.round(min) : null,
    max: Number.isFinite(max) ? Math.round(max) : null,
    distanceKm: series.at(-1) ? series.at(-1).dist / 1000 : 0,
  }
}
