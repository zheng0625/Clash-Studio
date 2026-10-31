import type { Edits } from './types'

/** Preserve explicit order, append new rules before MATCH/FINAL, and deduplicate. */
export function composeEditorRules(source: string[], edits: Edits, aiRules: string[], managed: (rule: string) => boolean): string[] {
  const removed = new Set(edits.removed_rules)
  const available = [...source.filter(rule => !removed.has(rule)), ...edits.added_rules]
  const availableSet = new Set(available)
  const orderedSet = new Set(edits.rule_order.filter(rule => availableSet.has(rule)))
  const ordered = [...orderedSet]
  const rest = available.filter(rule => !orderedSet.has(rule))
  const final = ordered.findIndex(rule => /^(MATCH|FINAL),/i.test(rule))
  const combined = final < 0 ? ordered.concat(rest) : ordered.slice(0, final).concat(rest, ordered.slice(final))
  return [...aiRules, ...new Set(combined.filter(rule => !managed(rule)))]
}
