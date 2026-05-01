import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'
import { buildTipNode } from '../src/lib/tooltip.js'

// Wire up a minimal DOM so document.createElement works in node --test.
const dom = new JSDOM('<!doctype html><html><body></body></html>')
globalThis.document = dom.window.document

// 1. Plain label → renders as text, no HTML elements injected.
{
  const node = buildTipNode('Day 3', 'Mather Campground')
  assert.equal(node.children.length, 2, 'two spans (num + label)')
  assert.equal(node.children[0].className, 'iti-tip-num')
  assert.equal(node.children[0].textContent, 'Day 3')
  assert.equal(node.children[1].className, 'iti-tip-label')
  assert.equal(node.children[1].textContent, 'Mather Campground')
}

// 2. The exploit payload: an injected <img onerror> must NOT become a real
//    <img> element. textContent flattens it to literal characters so Leaflet
//    paints it as text instead of a live image tag.
{
  const payload = '<img src=x onerror="window.__pwn=Date.now()">Mather Campground'
  const node = buildTipNode('Day 3', payload)
  // The label span exists, but its only child is a text node — no <img> got
  // parsed out of the user input.
  assert.equal(node.querySelector('img'), null, 'no <img> element from payload')
  assert.equal(node.children[1].textContent, payload, 'payload preserved as text')
}

// 3. Empty label → label span is omitted (matches old behaviour).
{
  const node = buildTipNode('Day 1', '')
  assert.equal(node.children.length, 1, 'only the num span when label is empty')
}

// 4. Day chip itself is also user-influenced (cumulative computed string) —
//    use textContent there too.
{
  const node = buildTipNode('<script>alert(1)</script>', 'safe')
  assert.equal(node.querySelector('script'), null, 'no <script> from chip')
  assert.equal(node.children[0].textContent, '<script>alert(1)</script>')
}

console.log('xss: OK')
