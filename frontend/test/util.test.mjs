// frontend/test/util.test.mjs
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { extractMarkerThumb, markdownExcerpt } from '../src/util.js'

test('extractMarkerThumb returns null for empty / no image', () => {
  assert.equal(extractMarkerThumb(null), null)
  assert.equal(extractMarkerThumb(''), null)
  assert.equal(extractMarkerThumb('just some text'), null)
})

test('extractMarkerThumb returns null for external image (not /uploads/)', () => {
  assert.equal(extractMarkerThumb('![pic](https://example.com/cat.jpg)'), null)
})

test('extractMarkerThumb extracts first /uploads/ image and derives thumb URL', () => {
  const r = extractMarkerThumb('text ![](/uploads/abc123.jpg) and more')
  assert.deepEqual(r, {
    full_url: '/uploads/abc123.jpg',
    thumb_url: '/uploads/abc123_thumb.jpg',
  })
})

test('extractMarkerThumb picks the FIRST upload, even if a remote precedes it', () => {
  const md = '![remote](https://e.com/x.png)\n\n![local](/uploads/xyz.jpg)'
  const r = extractMarkerThumb(md)
  assert.equal(r.full_url, '/uploads/xyz.jpg')
})

test('extractMarkerThumb handles .png extension correctly in thumb derivation', () => {
  const r = extractMarkerThumb('![](/uploads/foo.png)')
  assert.equal(r.thumb_url, '/uploads/foo_thumb.png')
})

test('markdownExcerpt strips formatting and truncates to maxLen', () => {
  const md = '# Title\n\n**bold** and _italic_ with ![pic](/uploads/x.jpg) in it.'
  assert.equal(markdownExcerpt(md, 80), 'Title bold and italic with  in it.')
})

test('markdownExcerpt returns empty string for null/empty input', () => {
  assert.equal(markdownExcerpt(null), '')
  assert.equal(markdownExcerpt(''), '')
})

test('markdownExcerpt truncates and appends ellipsis when over maxLen', () => {
  const long = 'word '.repeat(100)
  const out = markdownExcerpt(long, 30)
  assert(out.length <= 33)  // 30 + '…' (with possible trailing trim)
  assert(out.endsWith('…'))
})
