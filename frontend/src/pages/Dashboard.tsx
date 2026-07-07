import { useQuery } from '@tanstack/react-query'
import { subDays } from 'date-fns'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { KpiCard } from '../components/KpiCard'

const SEVERITY_STYLE: Record<string, string> = {
  high:   'bg-red-50 border-red-200 text-red-800',
  medium: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  low:    'bg-slate-50 border-slate-200 text-slate-600',
}

export function Dashboard() {
  const today    = new Date()
  const from30   = subDays(today, 30).toISOString()
  const toNow    = today.toISOString()

  const { data: fc } = useQuery({
    queryKey: ['food-cost', '30d'],
    queryFn:  () => api.get('/sales/food-cost', { params: { date_from: from30, date_to: toNow } }).then(r => r.data),
  })
  const { data: items } = useQuery({
    queryKey: ['profitability', '30d'],
    queryFn:  () => api.get('/sales/item-profitability', { params: { date_from: from30, date_to: toNow, limit: 10 } }).then(r => r.data),
  })
  const { data: alerts } = useQuery({
    queryKey: ['alerts'],
    queryFn:  () => api.get('/alerts', { params: { unread_only: true } }).then(r => r.data),
    refetchInterval: 60_000,
  })
  const { data: variance } = useQuery({
    queryKey: ['insights', 'variance', 'dashboard'],
    queryFn:  () => api.get('/insights/variance?window_days=7').then(r => r.data),
  })
  const { data: breakEven } = useQuery({
    queryKey: ['insights', 'break-even', 'dashboard'],
    queryFn:  () => api.get('/insights/break-even').then(r => r.data),
  })
  const { data: primeCost } = useQuery({
    queryKey: ['insights', 'prime-cost', 'dashboard'],
    queryFn:  () => api.get('/insights/prime-cost?window_days=28').then(r => r.data),
  })
  const { data: actionsData } = useQuery({
    queryKey: ['insights', 'actions'],
    queryFn:  () => api.get('/insights/actions').then(r => r.data),
    staleTime:       15 * 60 * 1000,   // actions are derived from daily data; 15 min is fine
    refetchInterval: 300_000,
  })

  const fcAlert = fc?.food_cost_pct != null && Number(fc.food_cost_pct) > 35

  const varianceFlagged = (variance as any[])?.filter((r: any) => r.recommended_action) ?? []
  const totalVarianceValue = varianceFlagged.reduce((s: number, r: any) => s + Math.abs(r.variance_value ?? 0), 0)
  const varianceAlert = varianceFlagged.length > 0

  const actionsList: any[] = (actionsData as any)?.actions ?? []

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <h1 className='text-2xl font-bold text-slate-800 mb-6'>Operations Dashboard</h1>

      {/* ── Today's actions ──────────────────────────────────────────────────── */}
      <div className='mb-6 bg-white rounded-xl shadow-sm p-5'>
        <h2 className='font-semibold text-slate-700 mb-3 text-sm uppercase tracking-wide'>Today's Actions</h2>
        {actionsList.length === 0 ? (
          <p className='text-slate-400 text-sm py-2 text-center'>
            {(actionsData as any)?.empty_msg ?? 'No actions needed — all metrics in range.'}
          </p>
        ) : (
          <div className='space-y-2'>
            {actionsList.map((a: any, i: number) => (
              <Link
                key={i}
                to={a.link_route}
                className={`flex items-start gap-3 border rounded-lg px-4 py-3 hover:opacity-90 transition-opacity ${SEVERITY_STYLE[a.severity] ?? SEVERITY_STYLE.low}`}
              >
                <span className='font-bold shrink-0 mt-0.5'>
                  {a.severity === 'high' ? '!' : a.severity === 'medium' ? '·' : '○'}
                </span>
                <span className='text-sm leading-snug'>{a.text}</span>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Alert banners (unread high/medium system alerts) */}
      {(alerts ?? []).length > 0 && (
        <div className='mb-6 space-y-2'>
          {(alerts as any[]).map((a: any) => (
            <div key={a.id} className={`p-3 rounded-lg text-sm flex gap-2 ${
              a.severity === 'high' ? 'bg-red-50 text-red-800' : 'bg-yellow-50 text-yellow-800'
            }`}>
              <span className='font-bold shrink-0'>{a.severity === 'high' ? '!' : '·'}</span>
              <div>
                <span>{a.message}</span>
                {/* Explanation sub-bullets */}
                {a.extra_data?.explanation && (() => {
                  const ex = a.extra_data.explanation
                  const bullets: string[] = []
                  for (const d of (ex.price_drivers ?? []).slice(0, 2))
                    bullets.push(`${d.ingredient} up ${d.pct_change}%`)
                  for (const d of (ex.mix_drivers ?? []).slice(0, 1))
                    bullets.push(`${d.item} FC ${d.fc_pct}%`)
                  if (ex.adj_driver)
                    bullets.push(`adjustments $${ex.adj_driver.today_total} (avg $${ex.adj_driver.daily_avg}/day)`)
                  return bullets.length > 0 ? (
                    <ul className='mt-1 ml-2 text-xs list-disc list-inside opacity-80'>
                      {bullets.map((b, bi) => <li key={bi}>{b}</li>)}
                    </ul>
                  ) : null
                })()}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* KPI row */}
      <div className='grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8'>
        <KpiCard
          label='Food Cost % (30d)'
          value={fc?.food_cost_pct != null ? `${Number(fc.food_cost_pct).toFixed(1)}%` : '—'}
          target='30%'
          alert={fcAlert}
        />
        <KpiCard
          label='Revenue (30d)'
          value={fc?.total_revenue != null ? `$${Number(fc.total_revenue).toLocaleString()}` : '—'}
        />
        <KpiCard
          label='Unread Alerts'
          value={alerts != null ? String((alerts as any[]).length) : '—'}
          alert={(alerts as any[])?.length > 0}
        />
        <KpiCard
          label='Prime Cost % (28d)'
          value={primeCost?.prime_cost_pct != null ? `${Number(primeCost.prime_cost_pct).toFixed(1)}%` : '—'}
          target='62%'
          alert={primeCost?.flag_over_62 === true}
        />
        <KpiCard
          label='Variance (7d)'
          value={variance != null ? (varianceFlagged.length > 0 ? `$${totalVarianceValue.toFixed(0)} flagged` : 'OK') : '—'}
          alert={varianceAlert}
        />
        <KpiCard
          label='Daily vs. Break-Even'
          value={
            breakEven?.data_gap
              ? 'Set fixed costs'
              : breakEven?.daily_surplus != null
                ? `${breakEven.daily_surplus >= 0 ? '+' : ''}$${Number(breakEven.daily_surplus).toFixed(0)}/day`
                : '—'
          }
          alert={breakEven != null && !breakEven.data_gap && (breakEven.daily_surplus ?? 0) < 0}
        />
      </div>

      {/* Profitability table */}
      {(items as any[])?.length > 0 && (
        <div className='bg-white rounded-xl p-5 shadow-sm'>
          <h2 className='font-semibold text-slate-700 mb-4'>Menu Item Profitability (30 days)</h2>
          <table className='w-full text-sm'>
            <thead>
              <tr className='text-left text-slate-400 text-xs uppercase tracking-wide border-b'>
                <th className='pb-2'>Item</th>
                <th className='pb-2 text-right'>Qty sold</th>
                <th className='pb-2 text-right'>Revenue</th>
                <th className='pb-2 text-right'>FC%</th>
                <th className='pb-2 text-right'>Gross profit</th>
              </tr>
            </thead>
            <tbody>
              {(items as any[]).map((item: any, i: number) => (
                <tr key={i} className='border-b border-slate-50 hover:bg-slate-50'>
                  <td className='py-2 font-medium'>{item.name ?? item.menu_item_id}</td>
                  <td className='py-2 text-right'>{item.quantity_sold}</td>
                  <td className='py-2 text-right'>${Number(item.revenue ?? 0).toFixed(2)}</td>
                  <td className={`py-2 text-right font-semibold ${Number(item.food_cost_pct) > 35 ? 'text-red-500' : 'text-green-600'}`}>
                    {Number(item.food_cost_pct ?? 0).toFixed(1)}%
                  </td>
                  <td className='py-2 text-right'>${Number(item.gross_profit ?? 0).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {items != null && (items as any[]).length === 0 && (
        <div className='bg-white rounded-xl p-8 shadow-sm text-center text-slate-400 text-sm'>
          No sales recorded in the last 30 days. Use Sales Entry to log your first batch.
        </div>
      )}
    </div>
  )
}
