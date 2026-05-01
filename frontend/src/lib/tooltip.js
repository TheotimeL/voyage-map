// Build a Leaflet permanent tooltip as a real DOM node so user-typed strings
// (day labels, pin titles) can never execute as HTML. Leaflet's bindTooltip
// accepts an HTMLElement and renders it as-is — using textContent on the
// inner spans means an injected `<img onerror>` becomes literal characters.
//
// Mirrors the previous string-template structure exactly so the existing CSS
// (.iti-tip-num / .iti-tip-label) keeps working with no styling changes.
export function buildTipNode(dayChip, cleanLabel) {
  const el = document.createElement('div')
  const num = document.createElement('span')
  num.className = 'iti-tip-num'
  num.textContent = dayChip
  el.appendChild(num)
  if (cleanLabel) {
    const lbl = document.createElement('span')
    lbl.className = 'iti-tip-label'
    lbl.textContent = cleanLabel
    el.appendChild(lbl)
  }
  return el
}
