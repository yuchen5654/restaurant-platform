import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

type Tab = 'variance' | 'menu-eng' | 'margins' | 'price-trends' | 'pars' | 'patterns' | 'sensitivity' | 'break-even'

const TABS: { id: Tab; label: string }[] = [
  { id: 'variance',     label: 'Variance' },
  { id: 'menu-eng',     label: 'Menu Eng' },
  { id: 'margins',      label: 'Margins' },
  { id: 'price-trends', label: 'Price Trends' },
  { id: 'pars',         label: 'Pars' },
  { id: 'patterns',     label: 'Patterns' },
  { id: 'sensitivity',  label: 'Sensitivity' },
  { id: 'break-even',   label: 'Break-Even' },
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

// ── Main Page ────────────────────────────────────────────────────────────────
export function InsightsPage() {
  const [tab, setTab] = useState<Tab>('variance')

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <h1 className='text-2xl font-bold text-slate-800 mb-6'>Insights</h1>

      {/* Tab bar */}
      <div className='flex gap-1 flex-wrap mb-6 border-b border-slate-200 pb-0'>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
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

      {tab === 'variance'     && <VarianceTab />}
      {tab === 'menu-eng'     && <MenuEngTab />}
      {tab === 'margins'      && <MarginsTab />}
      {tab === 'price-trends' && <PriceTrendsTab />}
      {tab === 'pars'         && <ParsTab />}
      {tab === 'patterns'     && <PatternsTab />}
      {tab === 'sensitivity'  && <SensitivityTab />}
      {tab === 'break-even'   && <BreakEvenTab />}
    </div>
  )
}
