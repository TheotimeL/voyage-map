// slippy-tile math + walker

const SUBDOMAINS = ['a', 'b', 'c', 'd']

export function lonLatToTile(lat, lng, z) {
  const n = 2 ** z
  const x = Math.floor(((lng + 180) / 360) * n)
  const latRad = (lat * Math.PI) / 180
  const y = Math.floor(
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n,
  )
  return { x, y }
}

export function tilesForBbox(bbox, [zMin, zMax]) {
  const out = []
  for (let z = zMin; z <= zMax; z++) {
    const tl = lonLatToTile(bbox.maxLat, bbox.minLng, z)
    const br = lonLatToTile(bbox.minLat, bbox.maxLng, z)
    for (let x = tl.x; x <= br.x; x++) {
      for (let y = tl.y; y <= br.y; y++) out.push({ z, x, y })
    }
  }
  return out
}

export function tileUrl({ z, x, y }, theme = 'light') {
  const sd = SUBDOMAINS[(x + y) % SUBDOMAINS.length]
  const style = theme === 'dark' ? 'dark_all' : 'light_all'
  return `https://${sd}.basemaps.cartocdn.com/${style}/${z}/${x}/${y}.png`
}

export async function preloadTiles(tiles, theme, { onProgress, signal, concurrency = 6 } = {}) {
  let done = 0, failed = 0
  const total = tiles.length
  const queue = tiles.slice()

  async function worker() {
    while (queue.length) {
      if (signal?.aborted) return
      const t = queue.shift()
      try {
        const res = await fetch(tileUrl(t, theme), { mode: 'cors', cache: 'force-cache' })
        if (!res.ok) failed++
      } catch { failed++ }
      done++
      onProgress?.({ done, failed, total })
    }
  }

  await Promise.all(Array.from({ length: concurrency }, worker))
  return { done, failed, total }
}
