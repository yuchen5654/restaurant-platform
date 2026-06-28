import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import api from '../api/client'

export function QuickSalesEntry() {
  const [date,    setDate]    = useState(format(new Date(), 'yyyy-MM-dd'))
  const [counts,  setCounts]  = useState<Record<string, string>>({})
  const [success, setSuccess] = useState(false)

  const { data: menuItems, isLoading } = useQuery({
    queryKey: ['menu-items'],
    queryFn:  () => api.get('/menu-items/').then(r => r.data),
  })

  const submit = useMutation({
    mutationFn: () => {
      const items = Object.entries(counts)
        .filter(([, qty]) => parseInt(qty) > 0)
        .map(([menu_item_id, qty]) => ({
          menu_item_id,
          quantity_sold: parseInt(qty),
          gross_revenue:
            parseInt(qty) *
            Number((menuItems as any[])?.find((m: any) => m.id === menu_item_id)?.menu_price ?? 0),
        }))
      // Use noon UTC to avoid date-boundary issues from local timezone offsets
      return api.post('/sales/record-batch', {
        business_date: new Date(date + 'T12:00:00Z').toISOString(),
        items,
      })
    },
    onSuccess: () => {
      setCounts({})
      setSuccess(true)
      setTimeout(() => setSuccess(false), 4000)
    },
  })

  // Group by category
  const byCategory: Record<string, any[]> = {}
  for (const item of (menuItems as any[]) ?? []) {
    const cat = item.category ?? 'Other'
    ;(byCategory[cat] ??= []).push(item)
  }

  const totalItems = Object.values(counts).filter(v => parseInt(v) > 0).length

  if (isLoading) return <div className='p-6 text-slate-400 text-sm'>Loading menu…</div>

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <div className='max-w-lg mx-auto'>
        <h1 className='text-2xl font-bold text-slate-800 mb-1'>End-of-Day Sales</h1>
        <p className='text-sm text-slate-500 mb-5'>
          Enter how many of each item you sold. Inventory depletes automatically on submit.
        </p>

        <div className='mb-5'>
          <label className='block text-xs font-semibold text-slate-600 mb-1'>Business date</label>
          <input type='date' value={date} onChange={e => setDate(e.target.value)}
            className='border border-slate-300 rounded-lg px-3 py-2 text-sm w-full
                       focus:outline-none focus:border-blue-400' />
        </div>

        {Object.entries(byCategory).map(([cat, items]) => (
          <div key={cat} className='mb-5'>
            <p className='text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2'>{cat}</p>
            <div className='bg-white rounded-xl shadow-sm divide-y divide-slate-50 overflow-hidden'>
              {items.map((item: any) => (
                <div key={item.id} className='flex items-center gap-3 px-4 py-3'>
                  <span className='flex-1 text-sm font-medium text-slate-700'>{item.name}</span>
                  <span className='text-xs text-slate-400 w-14 text-right'>
                    ${Number(item.menu_price).toFixed(2)}
                  </span>
                  <input
                    type='number' min='0' placeholder='0'
                    value={counts[item.id] ?? ''}
                    onChange={e => setCounts(p => ({ ...p, [item.id]: e.target.value }))}
                    className='w-16 text-center border border-slate-200 rounded-lg px-2 py-1.5 text-sm
                               focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200'
                  />
                </div>
              ))}
            </div>
          </div>
        ))}

        {(menuItems as any[])?.length === 0 && (
          <div className='bg-white rounded-xl p-6 text-center text-slate-400 text-sm shadow-sm mb-5'>
            No menu items yet — add some in Recipe Builder first.
          </div>
        )}

        {success && (
          <div className='mb-4 bg-green-50 border border-green-200 text-green-700 text-sm p-3 rounded-lg'>
            Sales recorded and inventory updated.
          </div>
        )}

        {submit.isError && (
          <div className='mb-4 bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded-lg'>
            Failed to record — check the API connection and try again.
          </div>
        )}

        <button
          onClick={() => submit.mutate()}
          disabled={submit.isPending || totalItems === 0}
          className='w-full bg-blue-600 text-white py-3 rounded-xl font-semibold
                     hover:bg-blue-700 disabled:opacity-50 transition-opacity'
        >
          {submit.isPending
            ? 'Recording…'
            : totalItems > 0
            ? `Record ${totalItems} Item${totalItems !== 1 ? 's' : ''} & Update Inventory`
            : 'Enter quantities above'}
        </button>
      </div>
    </div>
  )
}
