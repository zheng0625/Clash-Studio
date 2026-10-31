// Layout tier detection for the mobile shell (Android WebView and browser
// previews). The tier module marks <html data-mobile-tier="compact"|"tablet">
// from the usable CSS viewport, the orientation and the real Android platform
// identity together — never from physical resolution or the pointer type
// alone. Desktop windows leave the attribute unset, so the desktop shell and
// the user's palette stay intact; mobile.css keys every mobile rule off the
// attribute through :where() and keeps its old cascade specificity.
const legacy = matchMedia('(max-width:760px),(max-width:960px) and (max-height:500px) and (pointer:coarse)')
let android = /Android/i.test(navigator.userAgent)
let tier: 'compact' | 'tablet' | null = null
let keyboardShrunk = false
let stableWidth = window.innerWidth
let stableHeight = window.innerHeight

function focusedEditable(): boolean {
  const active = document.activeElement
  return active instanceof HTMLElement && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable)
}
function computeTier(): 'compact' | 'tablet' | null {
  const width = window.innerWidth
  // The native host pads its container by the IME inset, so a soft keyboard
  // shrinks the CSS viewport. While an editable keeps focus, tier decisions
  // stay on the pre-keyboard height so the shell does not fold mid-typing.
  const height = keyboardShrunk ? stableHeight : window.innerHeight
  if (android) {
    if (width > height && width >= 960 && height >= 600) return 'tablet'
    return 'compact'
  }
  // A small native desktop window still needs all seven Dock pages and
  // window controls. Android identity above takes precedence on mobile hosts.
  if ('__TAURI_INTERNALS__' in window) return null
  return legacy.matches ? 'compact' : null
}
function applyTier() {
  const next = computeTier()
  if (next === tier) return
  const root = document.documentElement
  // Switching tiers swaps the dock axis; pause the thumb transition for two
  // frames so the pill snaps to the new axis instead of flying diagonally.
  if (tier !== null && next !== null) {
    root.setAttribute('data-tier-switch', '')
    requestAnimationFrame(() => requestAnimationFrame(() => root.removeAttribute('data-tier-switch')))
  }
  tier = next
  if (next) root.setAttribute('data-mobile-tier', next)
  else root.removeAttribute('data-mobile-tier')
}
function onViewportChange() {
  const width = window.innerWidth, height = window.innerHeight
  const sameWidth = Math.abs(width - stableWidth) < 2
  if (focusedEditable() && sameWidth && height < stableHeight * 0.72) keyboardShrunk = true
  else if (!focusedEditable() || !sameWidth || height > stableHeight * 0.9) keyboardShrunk = false
  if (!keyboardShrunk) { stableWidth = width; stableHeight = height }
  applyTier()
}
/** Fold the backend platform identity (or UI workshop mock) into the tier. */
export function setMobilePlatformAndroid(value: boolean): void {
  if (android === value) return
  android = value
  applyTier()
}
window.addEventListener('resize', onViewportChange, { passive: true })
legacy.addEventListener?.('change', applyTier)
applyTier()
