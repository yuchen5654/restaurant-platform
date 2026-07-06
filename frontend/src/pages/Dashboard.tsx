import { useQuery } from '@tanstack/react-query'
import { subDays } from 'date-fns'
import api from '../api/client'
import { KpiCard } from '../components/KpiCard'

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

  const fcAlert = fc?.food_cost_pct != null && Number(fc.food_cost_pct) > 35

  const varianceFlagged = (variance as any[])?.filter((r: any) => r.recommended_action) ?? []
  const totalVarianceValue = varianceFlagged.reduce((s: number, r: any) => s + Math.abs(r.variance_value ?? 0), 0)
  const varianceAlert = varianceFlagged.length > 0

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <h1 className='text-2xl font-bold text-slate-800 mb-6'>Operations Dashboard</h1>

      {/* Alert banners */}
      {(alerts ?? []).length > 0 && (
        <div className='mb-6 space-y-2'>
          {(alerts as any[]).map((a: any) => (
            <div key={a.id} className={`p-3 rounded-lg text-sm flex gap-2 ${
              a.severity === 'high' ? 'bg-red-50 text-red-800' : 'bg-yellow-50 text-yellow-800'
            }`}>
              <span className='font-bold shrink-0'>{a.severity === 'high' ? '!' : '·'}</span>
              {a.message}
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
          label='Items Tracked'
          value={items != null ? String((items as any[]).length) : '—'}
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
