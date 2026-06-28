import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import api from '../api/client'

const REASONS = ['spoilage', 'prep_waste', 'over_portion', 'theft', 'comp', 'dropped'] as const

export function WasteLog() {
  const [ingredientId, setIngredientId] = useState('')
  const [quantity,     setQuantity]     = useState('')
  const [reason,       setReason]       = useState<string>('spoilage')
  const [notes,        setNotes]        = useState('')
  const [success,      setSuccess]      = useState(false)

  const { data: ingredients } = useQuery({
    queryKey: ['ingredients'],
    queryFn:  () => api.get('/ingredients/').then(r => r.data),
  })

  const selected = (ingredients as any[])?.find((i: any) => i.id === ingredientId)

  const submit = useMutation({
    mutationFn: () => api.post('/waste/', {
      ingredient_id: ingredientId,
      quantity:      parseFloat(quantity),
      reason,
      notes:         notes || null,
    }),
    onSuccess: () => {
      setIngredientId(''); setQuantity(''); setReason('spoilage'); setNotes('')
      setSuccess(true)
      setTimeout(() => setSuccess(false), 4000)
    },
  })

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <div className='max-w-lg mx-auto'>
        <h1 className='text-2xl font-bold text-slate-800 mb-1'>Log Waste</h1>
        <p className='text-sm text-slate-500 mb-6'>
          Record spoilage, prep waste, comps, over-portioning, or theft.
        </p>

        <div className='bg-white rounded-xl shadow-sm p-5 space-y-4'>
          {/* Ingredient */}
          <div>
            <label className='block text-xs font-semibold text-slate-600 mb-1'>Ingredient</label>
            <select value={ingredientId} onChange={e => setIngredientId(e.target.value)}
              className='w-full border border-slate-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:border-blue-400'>
              <option value=''>Select ingredient…</option>
              {(ingredients as any[])?.map((i: any) => (
                <option key={i.id} value={i.id}>{i.name} ({i.unit})</option>
              ))}
            </select>
            {selected && (
              <p className='text-xs text-slate-400 mt-1'>
                Current stock: {Number(selected.current_stock).toFixed(2)} {selected.unit}
              </p>
            )}
          </div>

          {/* Quantity + Reason */}
          <div className='flex gap-3'>
            <div className='flex-1'>
              <label className='block text-xs font-semibold text-slate-600 mb-1'>
                Quantity{selected ? ` (${selected.unit})` : ''}
              </label>
              <input type='number' min='0' step='0.01' value={quantity}
                onChange={e => setQuantity(e.target.value)}
                className='w-full border border-slate-300 rounded-lg px-3 py-2 text-sm
                           focus:outline-none focus:border-blue-400' />
            </div>
            <div className='flex-1'>
              <label className='block text-xs font-semibold text-slate-600 mb-1'>Reason</label>
              <select value={reason} onChange={e => setReason(e.target.value)}
                className='w-full border border-slate-300 rounded-lg px-3 py-2 text-sm
                           focus:outline-none focus:border-blue-400'>
                {REASONS.map(r => (
                  <option key={r} value={r}>{r.replace('_', ' ')}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className='block text-xs font-semibold text-slate-600 mb-1'>Notes (optional)</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
              placeholder='What happened?'
              className='w-full border border-slate-300 rounded-lg px-3 py-2 text-sm resize-none
                         focus:outline-none focus:border-blue-400' />
          </div>

          {success && (
            <div className='bg-green-50 border border-green-200 text-green-700 text-sm p-3 rounded-lg'>
              Waste logged and inventory updated.
            </div>
          )}

          <button onClick={() => submit.mutate()}
            disabled={!ingredientId || !quantity || submit.isPending}
            className='w-full bg-red-500 text-white py-3 rounded-xl font-semibold
                       hover:bg-red-600 disabled:opacity-50 transition-opacity'>
            {submit.isPending ? 'Logging…' : 'Log Waste'}
          </button>
        </div>
      </div>
    </div>
  )
}
