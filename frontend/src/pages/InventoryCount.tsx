import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

export function InventoryCount() {
  const qc = useQueryClient()
  const [counts,    setCounts]    = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)

  const { data: ingredients, isLoading } = useQuery({
    queryKey: ['ingredients'],
    queryFn:  () => api.get('/ingredients/').then(r => r.data),
  })

  const submit = useMutation({
    mutationFn: () => {
      const items = Object.entries(counts)
        .filter(([, q]) => q !== '')
        .map(([ingredient_id, q]) => ({ ingredient_id, quantity: parseFloat(q) }))
      return api.post('/inventory-counts/', { items })
    },
    onSuccess: () => {
      setCounts({})
      setSubmitted(true)
      setTimeout(() => setSubmitted(false), 4000)
      qc.invalidateQueries({ queryKey: ['ingredients'] })
    },
  })

  // Group by category
  const byCategory: Record<string, any[]> = {}
  for (const ing of (ingredients ?? []) as any[]) {
    const cat = ing.category ?? 'Uncategorised'
    ;(byCategory[cat] ??= []).push(ing)
  }

  if (isLoading) return <div className='p-6 text-slate-400 text-sm'>Loading ingredients…</div>

  const dirtyCount = Object.values(counts).filter(v => v !== '').length

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <div className='max-w-2xl mx-auto'>
        <h1 className='text-2xl font-bold text-slate-800 mb-1'>Inventory Count</h1>
        <p className='text-sm text-slate-500 mb-6'>
          Enter the quantity you physically counted. Leave blank to skip an item.
        </p>

        {Object.entries(byCategory).map(([cat, items]) => (
          <div key={cat} className='mb-6'>
            <p className='text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2'>{cat}</p>
            <div className='bg-white rounded-xl shadow-sm divide-y divide-slate-50 overflow-hidden'>
              {items.map((ing: any) => {
                const belowPar = ing.par_level != null && parseFloat(counts[ing.id] ?? ing.current_stock) < ing.par_level
                return (
                  <div key={ing.id} className='flex items-center px-4 py-3 gap-4'>
                    <div className='flex-1 min-w-0'>
                      <p className='text-sm font-medium text-slate-700 truncate'>{ing.name}</p>
                      <p className='text-xs text-slate-400 mt-0.5'>
                        On hand: {Number(ing.current_stock).toFixed(2)} {ing.unit}
                        {ing.par_level != null && ` · Par: ${Number(ing.par_level).toFixed(2)}`}
                      </p>
                    </div>
                    <div className='flex items-center gap-1.5 shrink-0'>
                      <input
                        type='number' min='0' step='0.01'
                        placeholder={Number(ing.current_stock).toFixed(2)}
                        value={counts[ing.id] ?? ''}
                        onChange={e => setCounts(p => ({ ...p, [ing.id]: e.target.value }))}
                        className={`w-20 text-right border rounded-lg px-2 py-1.5 text-sm
                                    focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200
                                    ${belowPar ? 'border-yellow-400 bg-yellow-50' : 'border-slate-200'}`}
                      />
                      <span className='text-xs text-slate-400 w-6'>{ing.unit}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}

        {submitted && (
          <div className='mb-4 bg-green-50 border border-green-200 text-green-700 text-sm p-3 rounded-lg'>
            Count submitted — inventory updated.
          </div>
        )}

        <button
          onClick={() => submit.mutate()}
          disabled={submit.isPending || dirtyCount === 0}
          className='w-full bg-blue-600 text-white py-3 rounded-xl font-semibold
                     hover:bg-blue-700 disabled:opacity-50 transition-opacity'
        >
          {submit.isPending ? 'Saving…' : `Submit Count (${dirtyCount} item${dirtyCount !== 1 ? 's' : ''})`}
        </button>
      </div>
    </div>
  )
}
