import { readdirSync, readFileSync } from 'node:fs'
import { expect, it } from 'vitest'

/*
 * Guards the HA-02 palette at the source level. Tailwind v4 silently emits nothing for a utility whose
 * token is undefined, so a wrong shade number renders with no colour at all, and it happily emits stock
 * palette colours that are not part of the design system. Neither shows up as a build or lint error, so
 * these checks walk the whole tree instead of a hand-maintained file list.
 */

const SRC = new URL('.', import.meta.url)
const TOKEN_FAMILIES = ['brand', 'ink', 'success', 'warning', 'danger', 'info']
const STOCK_FAMILIES = [
  'slate', 'gray', 'zinc', 'neutral', 'stone', 'red', 'orange', 'amber', 'yellow', 'lime', 'green',
  'emerald', 'teal', 'cyan', 'sky', 'blue', 'indigo', 'violet', 'purple', 'fuchsia', 'pink', 'rose',
]
const COLOR_PREFIX =
  '(?:text|bg|border|ring|accent|divide|from|via|to|outline|fill|stroke|shadow|decoration|caret|placeholder)'

function sourceFiles(): string[] {
  return readdirSync(SRC, { recursive: true, encoding: 'utf8' })
    .filter((name) => /\.tsx?$/.test(name))
    .map((name) => name.replace(/\\/g, '/'))
    .sort()
}

function read(relative: string): string {
  return readFileSync(new URL(relative, SRC), 'utf8')
}

const files = sourceFiles()

it('finds the source tree it is meant to scan', () => {
  // A broken glob would make every assertion below pass vacuously.
  expect(files).toContain('App.tsx')
  expect(files).toContain('routes/guards.tsx')
  expect(files.filter((f) => f.startsWith('components/ui/')).length).toBeGreaterThan(15)
})

it('only uses colour tokens that index.css actually defines', () => {
  const css = read('index.css')
  const defined = new Set(
    [...css.matchAll(/--color-([a-z]+-\d+)\s*:/g)].map((match) => match[1]),
  )
  expect(defined.size).toBeGreaterThan(20)

  const referenced = new RegExp(`\\b${COLOR_PREFIX}-(${TOKEN_FAMILIES.join('|')})-(\\d+)\\b`, 'g')
  const missing: string[] = []
  for (const file of files) {
    for (const match of read(file).matchAll(referenced)) {
      const token = `${match[1]}-${match[2]}`
      if (!defined.has(token)) missing.push(`${file}: ${match[0]} (no --color-${token})`)
    }
  }
  expect(missing).toEqual([])
})

it('keeps stock Tailwind palette colours out of every source file', () => {
  const stock = new RegExp(`\\b${COLOR_PREFIX}-(?:${STOCK_FAMILIES.join('|')})-\\d+\\b`, 'g')
  const offenders: string[] = []
  for (const file of files) {
    const hits = [...read(file).matchAll(stock)].map((match) => match[0])
    if (hits.length) offenders.push(`${file}: ${[...new Set(hits)].join(', ')}`)
  }
  expect(offenders).toEqual([])
})
