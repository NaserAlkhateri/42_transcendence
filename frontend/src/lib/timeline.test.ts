import { describe, expect, it } from 'vitest'

import { orderWithCorrections, type TimelineRecord } from './timeline'

function record(id: string, corrects: string | null = null): TimelineRecord {
  return {
    id, service_date: '2026-01-01', created_at: '2026-01-01T00:00:00Z', category: 'maintenance', work_codes: ['OIL_CHANGE'],
    odometer_km: 1000, organization_name: 'Falcon Bay Auto Care', is_mileage_flagged: false,
    corrects_record_id: corrects, correction_reason: corrects ? 'odometer' : null,
  }
}

const ids = (records: TimelineRecord[]) => records.map((r) => r.id)

describe('orderWithCorrections', () => {
  it('keeps the API order when nothing is corrected', () => {
    expect(ids(orderWithCorrections([record('a'), record('b')]))).toEqual(['a', 'b'])
  })

  it('moves a corrected original directly under its correction, wherever the dates put it', () => {
    // API order (newest first): the original carries a wrong, later date than its correction.
    const api = [record('newer'), record('original'), record('correction', 'original'), record('oldest')]
    expect(ids(orderWithCorrections(api))).toEqual(['newer', 'correction', 'original', 'oldest'])
  })

  it('stacks a chain: latest correction, then what it replaced, then the first original', () => {
    const api = [record('first'), record('fix1', 'first'), record('fix2', 'fix1')]
    expect(ids(orderWithCorrections(api))).toEqual(['fix2', 'fix1', 'first'])
  })

  it('shows a correction whose original is filtered out on its own', () => {
    expect(ids(orderWithCorrections([record('correction', 'hidden')]))).toEqual(['correction'])
  })
})
