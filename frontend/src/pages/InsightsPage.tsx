import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

type Tab = 'variance' | 'menu-eng' | 'margins' | 'price-trends' | 'pars' | 'patterns' | 'sensitivity' | 'break-even' | 'prime-cost' | 'channel' | 'waste' | 'adjustments' | 'benchmarks' | 'price-experiments'

const TABS: { id: Tab; label: string }[] = [
  { id: 'variance',          label: 'Variance' },
  { id: 'menu-eng',          label: 'Menu Eng' },
  { id: 'margins',           label: 'Margins' },
  { id: 'price-trends',      label: 'Price Trends' },
  { id: 'pars',              label: 'Pars' },
  { id: 'patterns',          label: 'Patterns' },
  { id: 'sensitivity',       label: 'Sensitivity' },
  { id: 'break-even',        label: 'Break-Even' },
  { id: 'prime-cost',        label: 'Prime Cost' },
  { id: 'channel',           label: 'Channels' },
  { id: 'waste',             label: 'Waste' },
  { id: 'adjustments',       label: 'Adjustments' },
  { id: 'benchmarks',        label: 'Benchmarks' },
  { id: 'price-experiments', label: 'Price Tests' },
]

const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function ActionBadge({ text }: { text: string | null | undefined }) {
  if (!text) return null
  return (
    <div className='mt-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 leading-relaxed'>
      {text}
    </div>
  )
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className='bg-white rounded-xl shadow-sm p-5'>
      <h2 className='font-semibold text-slate-700 mb-4 text-sm uppercase tracking-wide'>{title}</h2>
      {children}
    </div>
  )
}

function EmptyState({ msg }: { msg: string }) {
  return <p className='text-slate-400 text-sm py-6 text-center'>{msg}</p>
}

// ── Variance ────────────────────────────────────────────────────────────────
function VarianceTab() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['insights', 'variance'],
    queryFn: () => api.get('/insights/variance?window_days=7').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  const flagged = (data as any[]).filter((r: any) => r.recommended_action)
  const normal  = (data as any[]).filter((r: any) => !r.recommended_action && !r.data_gap)
  const gaps    = (data as any[]).filter((r: any) => r.data_gap)
  return (
    <SectionCard title='Theoretical vs. Actual Variance (7d)'>
      <p className='text-xs text-slate-400 mb-4'>
        Actual usage = opening count + received invoices − closing count.
        Theoretical = sum of depletion records in the window.
        Variance = actual − theoretical.
      </p>
      {flagged.length > 0 && (
        <div className='space-y-2 mb-4'>
          {flagged.map((r: any) => (
            <div key={r.ingredient_id} className='bg-red-50 border border-red-200 rounded-lg p-3'>
              <div className='flex justify-between text-sm font-medium text-red-800'>
                <span>{r.ingredient_name}</span>
                <span>${Math.abs(r.variance_value ?? 0).toFixed(2)} variance</span>
              </div>
              <div className='text-xs text-red-600 mt-1'>
                Theoretical {r.theoretical_qty?.toFixed(3)} {r.unit} · Actual {r.actual_qty?.toFixed(3)} {r.unit} · Δ {r.variance_qty?.toFixed(3)} {r.unit}
                {r.variance_pct != null && ` (${r.variance_pct.toFixed(1)}%)`}
              </div>
              <ActionBadge text={r.recommended_action} />
            </div>
          ))}
        </div>
      )}
      {normal.length > 0 && (
        <table className='w-full text-xs mb-4'>
          <thead>
            <tr className='text-left text-slate-400 border-b'>
              <th className='pb-1'>Ingredient</th>
              <th className='pb-1 text-right'>Theoretical</th>
              <th className='pb-1 text-right'>Actual</th>
              <th className='pb-1 text-right'>Variance</th>
              <th className='pb-1 text-right'>$Value</th>
            </tr>
          </thead>
          <tbody>
            {normal.map((r: any) => (
              <tr key={r.ingredient_id} className='border-b border-slate-50'>
                <td className='py-1'>{r.ingredient_name}</td>
                <td className='py-1 text-right'>{r.theoretical_qty?.toFixed(3)} {r.unit}</td>
                <td className='py-1 text-right'>{r.actual_qty?.toFixed(3)} {r.unit}</td>
                <td className='py-1 text-right'>{r.variance_qty?.toFixed(3)}</td>
                <td className='py-1 text-right text-green-600'>${r.variance_value?.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {gaps.length > 0 && (
        <p className='text-xs text-slate-400'>{gaps.length} ingredient(s) missing bracketing counts — log opening and closing inventory counts to enable variance.</p>
      )}
      {(data as any[]).length === 0 && <EmptyState msg='No ingredients found.' />}
    </SectionCard>
  )
}

// ── Menu Engineering ────────────────────────────────────────────────────────
const QUADRANT_COLORS: Record<string, string> = {
  Star:      'bg-green-100 text-green-800',
  Plowhorse: 'bg-blue-100 text-blue-800',
  Puzzle:    'bg-yellow-100 text-yellow-800',
  Dog:       'bg-slate-100 text-slate-500',
}

function MenuEngTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['insights', 'menu-eng'],
    queryFn: () => api.get('/insights/menu-engineering?window_days=28').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!data?.items?.length) return <EmptyState msg='No sales data in the last 28 days.' />
  return (
    <SectionCard title='Menu Engineering 2×2 (28d)'>
      <p className='text-xs text-slate-400 mb-4'>
        Popularity threshold: {data.popularity_threshold?.toFixed(1)} units · Margin threshold: ${data.margin_threshold?.toFixed(2)}/unit
      </p>
      <div className='space-y-2'>
        {(data.items as any[]).map((r: any) => (
          <div key={r.menu_item_id} className='border border-slate-100 rounded-lg p-3'>
            <div className='flex items-center justify-between'>
              <span className='font-medium text-sm'>{r.name}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${QUADRANT_COLORS[r.quadrant]}`}>{r.quadrant}</span>
            </div>
            <div className='text-xs text-slate-400 mt-1'>
              {r.units_sold} units · ${r.margin_dollars?.toFixed(2)}/unit margin
            </div>
            <ActionBadge text={r.recommended_action} />
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

// ── Contribution Margins ─────────────────────────────────────────────────────
function MarginsTab() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['insights', 'margins'],
    queryFn: () => api.get('/insights/contribution-margin?window_days=28').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!(data as any[]).length) return <EmptyState msg='No sales data in the last 28 days.' />
  const maxMargin = Math.max(...(data as any[]).map((r: any) => r.total_margin))
  return (
    <SectionCard title='Contribution Margin (28d)'>
      <p className='text-xs text-slate-400 mb-4'>Sorted by total margin = (price − plate cost) × units sold.</p>
      <div className='space-y-2'>
        {(data as any[]).map((r: any) => (
          <div key={r.menu_item_id}>
            <div className='flex justify-between text-sm'>
              <span className='font-medium'>{r.name}</span>
              <span className='text-green-700 font-semibold'>${r.total_margin?.toFixed(2)}</span>
            </div>
            <div className='h-2 bg-slate-100 rounded mt-1'>
              <div
                className='h-2 bg-green-400 rounded'
                style={{ width: `${maxMargin > 0 ? (r.total_margin / maxMargin) * 100 : 0}%` }}
              />
            </div>
            <div className='text-xs text-slate-400 mt-0.5'>
              {r.units_sold} units · ${r.price?.toFixed(2)} price · ${r.plate_cost?.toFixed(4)} cost · ${r.margin_dollars?.toFixed(4)}/unit
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

// ── Price Trends ─────────────────────────────────────────────────────────────
function PriceTrendsTab() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['insights', 'price-trends'],
    queryFn: () => api.get('/insights/price-trends').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!(data as any[]).length) return <EmptyState msg='No invoice history found.' />
  const flagged = (data as any[]).filter((r: any) => r.flag)
  const rest    = (data as any[]).filter((r: any) => !r.flag)
  return (
    <SectionCard title='Price Inflation & Trends'>
      {flagged.map((r: any) => (
        <div key={r.ingredient_id} className='bg-red-50 border border-red-200 rounded-lg p-3 mb-2'>
          <div className='flex justify-between text-sm font-medium text-red-800'>
            <span>{r.ingredient_name}</span>
            <span>+{r.change_60d_pct?.toFixed(1)}% (60d)</span>
          </div>
          <div className='text-xs text-red-600 mt-1'>
            Current avg ${r.current_avg_cost?.toFixed(4)} ·
            30d: {r.change_30d_pct != null ? `${r.change_30d_pct > 0 ? '+' : ''}${r.change_30d_pct?.toFixed(1)}%` : '—'} ·
            90d: {r.change_90d_pct != null ? `${r.change_90d_pct > 0 ? '+' : ''}${r.change_90d_pct?.toFixed(1)}%` : '—'}
          </div>
          <ActionBadge text={r.recommended_action} />
        </div>
      ))}
      {rest.length > 0 && (
        <table className='w-full text-xs mt-4'>
          <thead>
            <tr className='text-left text-slate-400 border-b'>
              <th className='pb-1'>Ingredient</th>
              <th className='pb-1 text-right'>Current avg</th>
              <th className='pb-1 text-right'>30d Δ</th>
              <th className='pb-1 text-right'>60d Δ</th>
              <th className='pb-1 text-right'>90d Δ</th>
            </tr>
          </thead>
          <tbody>
            {rest.map((r: any) => (
              <tr key={r.ingredient_id} className='border-b border-slate-50'>
                <td className='py-1'>{r.ingredient_name}</td>
                <td className='py-1 text-right'>${r.current_avg_cost?.toFixed(4)}</td>
                <td className='py-1 text-right'>{r.change_30d_pct != null ? `${r.change_30d_pct > 0 ? '+' : ''}${r.change_30d_pct?.toFixed(1)}%` : '—'}</td>
                <td className='py-1 text-right'>{r.change_60d_pct != null ? `${r.change_60d_pct > 0 ? '+' : ''}${r.change_60d_pct?.toFixed(1)}%` : '—'}</td>
                <td className='py-1 text-right'>{r.change_90d_pct != null ? `${r.change_90d_pct > 0 ? '+' : ''}${r.change_90d_pct?.toFixed(1)}%` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionCard>
  )
}

// ── Par Recommendations ──────────────────────────────────────────────────────
function ParsTab() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['insights', 'pars'],
    queryFn: () => api.get('/insights/par-recommendations').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!(data as any[]).length) return <EmptyState msg='No ingredients found.' />
  const actionable = (data as any[]).filter((r: any) => r.recommended_action)
  const ok         = (data as any[]).filter((r: any) => !r.recommended_action && !r.data_gap)
  return (
    <SectionCard title='Par-Level Optimization'>
      {actionable.map((r: any) => (
        <div key={r.ingredient_id} className={`border rounded-lg p-3 mb-2 ${r.data_gap ? 'border-slate-200 bg-slate-50' : 'border-amber-200 bg-amber-50'}`}>
          <div className='flex justify-between text-sm font-medium'>
            <span>{r.ingredient_name}</span>
            <span className='text-slate-500'>par: {r.current_par != null ? `${r.current_par} ${r.unit}` : 'not set'}</span>
          </div>
          {!r.data_gap && (
            <div className='text-xs text-slate-500 mt-1'>
              velocity {r.daily_velocity?.toFixed(3)} {r.unit}/day · {r.cover_days?.toFixed(1)}d cover · suggested: {r.suggested_par} {r.unit}
            </div>
          )}
          <ActionBadge text={r.recommended_action} />
        </div>
      ))}
      {ok.length > 0 && (
        <p className='text-xs text-slate-400 mt-4'>{ok.length} ingredient(s) within target cover-day range.</p>
      )}
    </SectionCard>
  )
}

// ── Sales Patterns ───────────────────────────────────────────────────────────
function PatternsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['insights', 'patterns'],
    queryFn: () => api.get('/insights/sales-patterns?window_days=28').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!data?.dow?.length) return <EmptyState msg='No sales data in the last 28 days.' />
  const maxRev = Math.max(...data.dow.map((d: any) => d.revenue))
  return (
    <SectionCard title='Day-of-Week & Daypart Patterns (28d)'>
      <div className='mb-6'>
        <h3 className='text-xs font-semibold text-slate-500 uppercase mb-2'>Day of Week</h3>
        <div className='space-y-1'>
          {data.dow.map((d: any) => (
            <div key={d.weekday} className='flex items-center gap-2 text-xs'>
              <span className='w-8 text-slate-500'>{d.weekday_name}</span>
              <div className='flex-1 h-4 bg-slate-100 rounded'>
                <div
                  className='h-4 bg-blue-400 rounded'
                  style={{ width: `${maxRev > 0 ? (d.revenue / maxRev) * 100 : 0}%` }}
                />
              </div>
              <span className='w-12 text-right text-slate-600'>${d.revenue?.toFixed(0)}</span>
              <span className={`w-12 text-right font-semibold ${d.index >= 1.2 ? 'text-green-600' : d.index < 0.8 ? 'text-red-500' : 'text-slate-500'}`}>
                {d.index?.toFixed(2)}×
              </span>
            </div>
          ))}
        </div>
      </div>
      {data.coverage_pct > 0 ? (
        <div>
          <h3 className='text-xs font-semibold text-slate-500 uppercase mb-2'>
            Daypart ({(data.coverage_pct * 100).toFixed(0)}% of rows have timestamps)
          </h3>
          <div className='space-y-1'>
            {data.daypart.map((d: any) => {
              const maxDp = Math.max(...data.daypart.map((x: any) => x.revenue))
              return (
                <div key={d.daypart} className='flex items-center gap-2 text-xs'>
                  <span className='w-20 text-slate-500 capitalize'>{d.daypart}</span>
                  <div className='flex-1 h-4 bg-slate-100 rounded'>
                    <div
                      className='h-4 bg-indigo-400 rounded'
                      style={{ width: `${maxDp > 0 ? (d.revenue / maxDp) * 100 : 0}%` }}
                    />
                  </div>
                  <span className='w-16 text-right text-slate-600'>${d.revenue?.toFixed(0)} · {d.units}u</span>
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        <p className='text-xs text-slate-400 mt-4'>Daypart breakdown requires timestamped sales (POS ingestion). Quick-entry sales are date-only.</p>
      )}
    </SectionCard>
  )
}

// ── Cost Sensitivity ─────────────────────────────────────────────────────────
function SensitivityTab() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['insights', 'sensitivity'],
    queryFn: () => api.get('/insights/cost-sensitivity?shock_pct=10').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!(data as any[]).length) return <EmptyState msg='No recipe-linked ingredients with sales data found.' />
  const max = Math.max(...(data as any[]).map((r: any) => r.exposure_dollars))
  return (
    <SectionCard title='Cost Sensitivity — 10% Price Shock (28d)'>
      <p className='text-xs text-slate-400 mb-4'>Margin dollars lost if each ingredient rises 10%, ranked by exposure.</p>
      <div className='space-y-3'>
        {(data as any[]).map((r: any) => (
          <div key={r.ingredient_id}>
            <div className='flex justify-between text-sm'>
              <span className='font-medium'>{r.ingredient_name}</span>
              <span className='text-red-600 font-semibold'>-${r.exposure_dollars?.toFixed(2)}</span>
            </div>
            <div className='h-2 bg-slate-100 rounded mt-1'>
              <div className='h-2 bg-red-400 rounded' style={{ width: `${max > 0 ? (r.exposure_dollars / max) * 100 : 0}%` }} />
            </div>
            <ActionBadge text={r.recommended_action} />
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

// ── Break-Even ───────────────────────────────────────────────────────────────
function BreakEvenTab() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['insights', 'break-even'],
    queryFn: () => api.get('/insights/break-even').then(r => r.data),
  })
  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['insights', 'settings'],
    queryFn: () => api.get('/insights/settings').then(r => r.data),
  })
  const [fixedCosts, setFixedCosts] = useState('')
  const [saving, setSaving] = useState(false)

  const saveFixed = async () => {
    setSaving(true)
    await api.patch('/insights/settings', { monthly_fixed_costs: parseFloat(fixedCosts) })
    await qc.invalidateQueries({ queryKey: ['insights', 'break-even'] })
    await qc.invalidateQueries({ queryKey: ['insights', 'settings'] })
    setFixedCosts('')
    setSaving(false)
  }

  if (isLoading || settingsLoading) return <EmptyState msg='Loading…' />

  return (
    <SectionCard title='Break-Even Analysis'>
      {data?.data_gap ? (
        <div>
          <p className='text-amber-700 text-sm bg-amber-50 px-3 py-2 rounded-lg mb-4'>{data.data_gap}</p>
          <div className='flex gap-2'>
            <input
              type='number'
              placeholder='Monthly fixed costs ($)'
              value={fixedCosts}
              onChange={e => setFixedCosts(e.target.value)}
              className='border border-slate-200 rounded px-3 py-1.5 text-sm flex-1'
            />
            <button
              onClick={saveFixed}
              disabled={saving || !fixedCosts}
              className='px-4 py-1.5 bg-blue-600 text-white rounded text-sm disabled:opacity-50'
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      ) : (
        <div>
          <div className='grid grid-cols-3 gap-4 mb-6'>
            <div className='text-center p-4 bg-slate-50 rounded-lg'>
              <div className='text-2xl font-bold text-slate-800'>${data?.daily_breakeven?.toFixed(0)}</div>
              <div className='text-xs text-slate-400 mt-1'>Daily break-even</div>
            </div>
            <div className='text-center p-4 bg-slate-50 rounded-lg'>
              <div className='text-2xl font-bold text-slate-800'>${data?.avg_daily_revenue?.toFixed(0)}</div>
              <div className='text-xs text-slate-400 mt-1'>Avg daily revenue (30d)</div>
            </div>
            <div className={`text-center p-4 rounded-lg ${(data?.daily_surplus ?? 0) >= 0 ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className={`text-2xl font-bold ${(data?.daily_surplus ?? 0) >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                {(data?.daily_surplus ?? 0) >= 0 ? '+' : ''}${data?.daily_surplus?.toFixed(0)}
              </div>
              <div className='text-xs text-slate-400 mt-1'>Daily surplus / shortfall</div>
            </div>
          </div>
          <div className='flex gap-2'>
            <input
              type='number'
              placeholder={`Update monthly fixed costs (currently $${settings?.monthly_fixed_costs?.toFixed(0)})`}
              value={fixedCosts}
              onChange={e => setFixedCosts(e.target.value)}
              className='border border-slate-200 rounded px-3 py-1.5 text-sm flex-1'
            />
            <button
              onClick={saveFixed}
              disabled={saving || !fixedCosts}
              className='px-4 py-1.5 bg-blue-600 text-white rounded text-sm disabled:opacity-50'
            >
              {saving ? 'Saving…' : 'Update'}
            </button>
          </div>
        </div>
      )}
    </SectionCard>
  )
}

// ── Prime Cost ───────────────────────────────────────────────────────────────
function PrimeCostTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['insights', 'prime-cost'],
    queryFn: () => api.get('/insights/prime-cost?window_days=28').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (data?.data_gap && !data.prime_cost_pct) return (
    <SectionCard title='Prime Cost (28d)'>
      <p className='text-amber-700 text-sm bg-amber-50 px-3 py-2 rounded-lg'>{data.data_gap}</p>
    </SectionCard>
  )
  const over62 = data?.flag_over_62
  return (
    <SectionCard title='Prime Cost (28d)'>
      <div className='grid grid-cols-3 gap-4 mb-6'>
        <div className='text-center p-4 bg-slate-50 rounded-lg'>
          <div className='text-2xl font-bold text-slate-800'>{data?.food_cost_pct?.toFixed(1) ?? '—'}%</div>
          <div className='text-xs text-slate-400 mt-1'>Food cost %</div>
        </div>
        <div className='text-center p-4 bg-slate-50 rounded-lg'>
          <div className='text-2xl font-bold text-slate-800'>{data?.labor_pct?.toFixed(1) ?? '—'}%</div>
          <div className='text-xs text-slate-400 mt-1'>Labor %</div>
        </div>
        <div className={`text-center p-4 rounded-lg ${over62 ? 'bg-red-50' : 'bg-green-50'}`}>
          <div className={`text-2xl font-bold ${over62 ? 'text-red-700' : 'text-green-700'}`}>
            {data?.prime_cost_pct?.toFixed(1) ?? '—'}%
          </div>
          <div className='text-xs text-slate-400 mt-1'>Prime cost {over62 ? '— above 62% target' : '— within target'}</div>
        </div>
      </div>
      {data?.data_gap && <p className='text-xs text-amber-600 mb-4'>{data.data_gap}</p>}
      {data?.sales_per_labor_hour_by_dow?.length > 0 && (
        <div>
          <h3 className='text-xs font-semibold text-slate-500 uppercase mb-2'>Sales per Labor Hour by Day</h3>
          <table className='w-full text-xs'>
            <thead>
              <tr className='text-left text-slate-400 border-b'>
                <th className='pb-1'>Day</th>
                <th className='pb-1 text-right'>$/labor hr</th>
              </tr>
            </thead>
            <tbody>
              {(data.sales_per_labor_hour_by_dow as any[]).map((d: any) => (
                <tr key={d.weekday} className='border-b border-slate-50'>
                  <td className='py-1'>{d.weekday_name}</td>
                  <td className='py-1 text-right'>{d.sales_per_labor_hour != null ? `$${d.sales_per_labor_hour.toFixed(2)}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}

// ── Channel Profitability ────────────────────────────────────────────────────
function ChannelTab() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['insights', 'channel'],
    queryFn: () => api.get('/insights/channel-profitability?window_days=28').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!(data as any[]).length) return (
    <SectionCard title='Channel Profitability (28d)'>
      <EmptyState msg='No channel-tagged sales in the last 28 days. Set a channel in Sales Entry.' />
    </SectionCard>
  )
  return (
    <SectionCard title='Channel Profitability (28d)'>
      <div className='space-y-3'>
        {(data as any[]).map((r: any) => (
          <div key={r.channel} className={`border rounded-lg p-3 ${r.net_contribution < 0 ? 'border-red-200 bg-red-50' : 'border-slate-100'}`}>
            <div className='flex items-center justify-between text-sm font-medium'>
              <span className='capitalize'>{r.channel}</span>
              <span className={r.net_contribution < 0 ? 'text-red-700' : 'text-green-700'}>
                Net ${r.net_contribution?.toFixed(2)}
              </span>
            </div>
            <div className='text-xs text-slate-400 mt-1 grid grid-cols-3 gap-2'>
              <span>Revenue: ${r.revenue?.toFixed(2)}</span>
              <span>Food cost: ${r.food_cost?.toFixed(2)}</span>
              <span>Commission: ${r.commission?.toFixed(2)}</span>
            </div>
            <div className='text-xs text-slate-500 mt-0.5'>Per-order net: ${r.per_order_net?.toFixed(2)}</div>
            <ActionBadge text={r.action} />
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

// ── Waste Decomposition ──────────────────────────────────────────────────────
function WasteTab() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['insights', 'waste'],
    queryFn: () => api.get('/insights/waste-decomposition?window_days=28').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!(data as any[]).length) return (
    <SectionCard title='Waste Decomposition (28d)'>
      <EmptyState msg='No waste logs in the last 28 days.' />
    </SectionCard>
  )
  const maxDollars = Math.max(...(data as any[]).map((r: any) => r.waste_dollars))
  return (
    <SectionCard title='Waste Decomposition (28d)'>
      <div className='space-y-3'>
        {(data as any[]).map((r: any) => (
          <div key={r.reason}>
            <div className='flex justify-between text-sm'>
              <span className='font-medium capitalize'>{r.reason}</span>
              <span className='text-red-600 font-semibold'>-${r.waste_dollars?.toFixed(2)}</span>
            </div>
            <div className='h-2 bg-slate-100 rounded mt-1'>
              <div className='h-2 bg-red-400 rounded' style={{ width: `${maxDollars > 0 ? (r.waste_dollars / maxDollars) * 100 : 0}%` }} />
            </div>
            <div className='text-xs text-slate-400 mt-0.5'>{r.waste_qty?.toFixed(3)} units wasted</div>
            <ActionBadge text={r.recommended_action} />
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

// ── Adjustments ──────────────────────────────────────────────────────────────
function AdjustmentsTab() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['insights', 'adjustments'],
    queryFn: () => api.get('/insights/adjustments?window_days=28').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!(data as any[]).length) return (
    <SectionCard title='Adjustments Report (28d)'>
      <EmptyState msg='No adjustments logged in the last 28 days.' />
    </SectionCard>
  )
  return (
    <SectionCard title='Adjustments Report (28d)'>
      <div className='space-y-3'>
        {(data as any[]).map((r: any) => (
          <div key={r.adjustment_type} className={`border rounded-lg p-3 ${r.flag_high ? 'border-red-200 bg-red-50' : 'border-slate-100'}`}>
            <div className='flex items-center justify-between text-sm font-medium'>
              <span className='capitalize'>{r.adjustment_type}</span>
              <span className={r.flag_high ? 'text-red-700' : 'text-slate-700'}>
                ${r.total_amount?.toFixed(2)}
              </span>
            </div>
            <div className='text-xs text-slate-400 mt-1'>
              {r.count} occurrence{r.count !== 1 ? 's' : ''}
              {r.pct_of_revenue != null && ` · ${r.pct_of_revenue.toFixed(1)}% of revenue`}
            </div>
            <ActionBadge text={r.recommended_action} />
          </div>
        ))}
      </div>
    </SectionCard>
  )
}

// ── Benchmarks ───────────────────────────────────────────────────────────────
function BenchmarksTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['insights', 'benchmarks'],
    queryFn: () => api.get('/insights/benchmarks').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  return (
    <SectionCard title='Peer Benchmarks'>
      <p className='text-xs text-slate-400 mb-4'>{data?.caveat}</p>
      {(!data?.benchmarks?.length || data.benchmarks.every((r: any) => r.p50 == null)) ? (
        <EmptyState msg='Not enough peer data yet — benchmarks appear once 5+ restaurants have data.' />
      ) : (
        <div className='space-y-4'>
          {(data.benchmarks as any[]).filter((r: any) => r.p50 != null).map((r: any) => {
            const own  = r.own_value
            const p25  = r.p25
            const p75  = r.p75
            const p50  = r.p50
            const pctPos = own != null && p25 != null && p75 != null && p75 !== p25
              ? Math.min(100, Math.max(0, ((own - p25) / (p75 - p25)) * 100))
              : null
            return (
              <div key={r.metric}>
                <div className='flex justify-between text-sm mb-1'>
                  <span className='font-medium text-slate-700'>{r.metric.replace(/_/g, ' ')}</span>
                  <span className='text-slate-500'>
                    own: <span className='font-semibold text-slate-800'>
                      {own != null ? own.toFixed(1) : '—'}
                    </span>
                    {r.n != null && <span className='text-xs text-slate-400 ml-2'>n={r.n}</span>}
                  </span>
                </div>
                {/* p25–p75 band */}
                <div className='relative h-4 bg-slate-100 rounded'>
                  <div
                    className='absolute h-4 bg-blue-100 rounded'
                    style={{ left: '0%', right: '0%' }}
                  />
                  {/* p50 marker */}
                  <div
                    className='absolute top-0 h-4 w-0.5 bg-blue-400'
                    style={{ left: `${p25 != null && p75 != null && p75 !== p25 ? ((p50 - p25) / (p75 - p25)) * 100 : 50}%` }}
                  />
                  {/* own value marker */}
                  {pctPos != null && (
                    <div
                      className='absolute top-0 h-4 w-1 bg-slate-800 rounded'
                      style={{ left: `${pctPos}%` }}
                    />
                  )}
                </div>
                <div className='flex justify-between text-xs text-slate-400 mt-0.5'>
                  <span>p25: {p25?.toFixed(1)}</span>
                  <span>p50: {p50?.toFixed(1)}</span>
                  <span>p75: {p75?.toFixed(1)}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </SectionCard>
  )
}

// ── Price Experiments ────────────────────────────────────────────────────────
const VERDICT_STYLE: Record<string, string> = {
  'price change maintained or improved margin': 'text-green-700 bg-green-50',
  'volume dropped significantly — consider reverting':   'text-red-700 bg-red-50',
  'margin declined — monitor':                           'text-amber-700 bg-amber-50',
  'insufficient data':                                   'text-slate-500 bg-slate-50',
}

function PriceExperimentsTab() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['insights', 'price-experiments'],
    queryFn: () => api.get('/insights/price-experiments').then(r => r.data),
  })
  if (isLoading) return <EmptyState msg='Loading…' />
  if (!(data as any[]).length) return (
    <SectionCard title='Price Test & Learn'>
      <EmptyState msg='No price changes yet — use the menu item PATCH endpoint to record a price change and see before/after analysis here after 14 days.' />
    </SectionCard>
  )
  return (
    <SectionCard title='Price Test & Learn'>
      <p className='text-xs text-slate-400 mb-4'>
        Before/after analysis for price changes older than 14 days. Windows clamped by neighboring events, max 28d each.
      </p>
      <div className='space-y-4'>
        {(data as any[]).map((r: any) => {
          const verdictStyle = VERDICT_STYLE[r.verdict] ?? 'text-slate-500 bg-slate-50'
          return (
            <div key={r.event_id} className='border border-slate-100 rounded-lg p-4'>
              <div className='flex items-center justify-between mb-2'>
                <span className='font-semibold text-slate-800'>{r.item_name}</span>
                <span className='text-xs text-slate-400'>
                  {new Date(r.changed_at).toLocaleDateString()}
                </span>
              </div>
              <div className='text-sm text-slate-600 mb-2'>
                ${r.old_price?.toFixed(2)} → ${r.new_price?.toFixed(2)}
                {r.price_change_pct != null && (
                  <span className={`ml-2 font-semibold ${r.price_change_pct >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                    {r.price_change_pct >= 0 ? '+' : ''}{r.price_change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
              {/* Before/after mini bars */}
              <div className='grid grid-cols-2 gap-3 text-xs mb-3'>
                <div className='bg-slate-50 rounded p-2'>
                  <div className='text-slate-400 mb-1'>Before ({r.before_days}d)</div>
                  <div>{r.before_units_per_day?.toFixed(2)} units/day</div>
                  <div>${r.before_margin_per_day?.toFixed(2)}/day margin</div>
                </div>
                <div className='bg-slate-50 rounded p-2'>
                  <div className='text-slate-400 mb-1'>After ({r.after_days}d)</div>
                  <div>
                    {r.after_units_per_day?.toFixed(2)} units/day
                    {r.units_delta_pct != null && (
                      <span className={`ml-1 ${r.units_delta_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ({r.units_delta_pct >= 0 ? '+' : ''}{r.units_delta_pct?.toFixed(1)}%)
                      </span>
                    )}
                  </div>
                  <div>
                    ${r.after_margin_per_day?.toFixed(2)}/day margin
                    {r.margin_delta_pct != null && (
                      <span className={`ml-1 ${r.margin_delta_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ({r.margin_delta_pct >= 0 ? '+' : ''}{r.margin_delta_pct?.toFixed(1)}%)
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className={`text-xs px-3 py-2 rounded ${verdictStyle}`}>
                {r.verdict}
              </div>
            </div>
          )
        })}
      </div>
    </SectionCard>
  )
}

const VALID_TABS = new Set(TABS.map(t => t.id))

// ── Main Page ────────────────────────────────────────────────────────────────
export function InsightsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab') as Tab | null
  const [tab, setTab] = useState<Tab>(
    tabParam && VALID_TABS.has(tabParam) ? tabParam : 'variance'
  )

  // Keep tab in sync when the URL param changes (e.g. back/forward navigation
  // or a Dashboard action link clicked while already on the Insights page).
  useEffect(() => {
    const p = searchParams.get('tab') as Tab | null
    if (p && VALID_TABS.has(p) && p !== tab) setTab(p)
  }, [searchParams])

  const selectTab = (id: Tab) => {
    setTab(id)
    setSearchParams({ tab: id }, { replace: true })
  }

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <h1 className='text-2xl font-bold text-slate-800 mb-6'>Insights</h1>

      {/* Tab bar */}
      <div className='flex gap-1 flex-wrap mb-6 border-b border-slate-200 pb-0'>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => selectTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'variance'          && <VarianceTab />}
      {tab === 'menu-eng'          && <MenuEngTab />}
      {tab === 'margins'           && <MarginsTab />}
      {tab === 'price-trends'      && <PriceTrendsTab />}
      {tab === 'pars'              && <ParsTab />}
      {tab === 'patterns'          && <PatternsTab />}
      {tab === 'sensitivity'       && <SensitivityTab />}
      {tab === 'break-even'        && <BreakEvenTab />}
      {tab === 'prime-cost'        && <PrimeCostTab />}
      {tab === 'channel'           && <ChannelTab />}
      {tab === 'waste'             && <WasteTab />}
      {tab === 'adjustments'       && <AdjustmentsTab />}
      {tab === 'benchmarks'        && <BenchmarksTab />}
      {tab === 'price-experiments' && <PriceExperimentsTab />}
    </div>
  )
}
