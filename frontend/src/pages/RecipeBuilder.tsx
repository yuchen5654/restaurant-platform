import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

export function RecipeBuilder() {
  const qc = useQueryClient()
  const [selectedId,   setSelectedId]   = useState<string | null>(null)
  const [showNew,      setShowNew]       = useState(false)
  const [newName,      setNewName]       = useState('')
  const [newCategory,  setNewCategory]   = useState('')
  const [newPrice,     setNewPrice]      = useState('')
  const [lineIngId,    setLineIngId]     = useState('')
  const [lineQty,      setLineQty]       = useState('')
  const [lineUnit,     setLineUnit]      = useState('')

  const { data: menuItems } = useQuery({
    queryKey: ['menu-items'],
    queryFn:  () => api.get('/menu-items/').then(r => r.data),
  })
  const { data: ingredients } = useQuery({
    queryKey: ['ingredients'],
    queryFn:  () => api.get('/ingredients/').then(r => r.data),
  })
  const { data: fc } = useQuery({
    queryKey: ['menu-item-fc', selectedId],
    queryFn:  () => api.get(`/menu-items/${selectedId}/food-cost`).then(r => r.data),
    enabled:  !!selectedId,
  })

  const createItem = useMutation({
    mutationFn: () => api.post('/menu-items/', {
      name: newName, category: newCategory || null, menu_price: parseFloat(newPrice),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['menu-items'] })
      setNewName(''); setNewCategory(''); setNewPrice(''); setShowNew(false)
    },
  })

  const addLine = useMutation({
    mutationFn: () => api.post(`/menu-items/${selectedId}/recipe-lines`, {
      ingredient_id: lineIngId,
      quantity:      parseFloat(lineQty),
      unit:          lineUnit,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['menu-item-fc', selectedId] })
      setLineIngId(''); setLineQty(''); setLineUnit('')
    },
  })

  return (
    <div className='flex h-full bg-slate-50'>
      {/* Left panel — item list */}
      <div className='w-60 shrink-0 bg-white border-r border-slate-200 flex flex-col'>
        <div className='px-4 py-3 border-b border-slate-100 flex items-center justify-between'>
          <span className='font-semibold text-slate-700 text-sm'>Menu Items</span>
          <button onClick={() => setShowNew(v => !v)}
            className='text-xs text-blue-600 font-semibold hover:underline'>
            {showNew ? 'Cancel' : '+ New'}
          </button>
        </div>

        {showNew && (
          <div className='p-3 border-b border-slate-100 space-y-2'>
            <input placeholder='Name' value={newName} onChange={e => setNewName(e.target.value)}
              className='w-full border rounded-lg px-2 py-1.5 text-xs' />
            <input placeholder='Category (optional)' value={newCategory} onChange={e => setNewCategory(e.target.value)}
              className='w-full border rounded-lg px-2 py-1.5 text-xs' />
            <input type='number' placeholder='Price $' value={newPrice} onChange={e => setNewPrice(e.target.value)}
              className='w-full border rounded-lg px-2 py-1.5 text-xs' />
            <button onClick={() => createItem.mutate()} disabled={!newName || !newPrice}
              className='w-full bg-blue-600 text-white text-xs py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50'>
              Save
            </button>
          </div>
        )}

        <ul className='flex-1 overflow-auto divide-y divide-slate-50'>
          {(menuItems as any[])?.map((item: any) => (
            <li key={item.id}>
              <button onClick={() => setSelectedId(item.id)}
                className={`w-full text-left px-4 py-3 transition-colors hover:bg-slate-50 ${
                  selectedId === item.id ? 'bg-blue-50' : ''
                }`}>
                <p className={`text-sm font-medium ${selectedId === item.id ? 'text-blue-700' : 'text-slate-700'}`}>
                  {item.name}
                </p>
                <p className='text-xs text-slate-400 mt-0.5'>${Number(item.menu_price).toFixed(2)}</p>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* Right panel — recipe lines */}
      <div className='flex-1 p-6 overflow-auto'>
        {!selectedId && (
          <div className='h-full flex items-center justify-center'>
            <p className='text-slate-400 text-sm'>Select a menu item to build its recipe</p>
          </div>
        )}

        {selectedId && fc && (
          <>
            <div className='mb-5'>
              <h1 className='text-xl font-bold text-slate-800'>{fc.name}</h1>
              <p className='text-sm text-slate-500 mt-0.5'>
                Sell price: <span className='font-medium'>${Number(fc.menu_price ?? 0).toFixed(2)}</span>
                {' · '}Theoretical cost: <span className='font-medium'>${Number(fc.theoretical_cost ?? 0).toFixed(4)}</span>
                {' · '}FC%:{' '}
                <span className={`font-bold ${Number(fc.food_cost_pct) > 35 ? 'text-red-500' : 'text-green-600'}`}>
                  {fc.food_cost_pct ?? '—'}%
                </span>
              </p>
            </div>

            {/* Recipe lines table */}
            <div className='bg-white rounded-xl shadow-sm overflow-hidden mb-5'>
              <table className='w-full text-sm'>
                <thead>
                  <tr className='text-xs text-slate-400 uppercase tracking-wide border-b bg-slate-50'>
                    <th className='text-left px-4 py-2'>Ingredient</th>
                    <th className='text-right px-4 py-2'>Qty</th>
                    <th className='px-4 py-2'>Unit</th>
                    <th className='text-right px-4 py-2'>Line cost</th>
                  </tr>
                </thead>
                <tbody className='divide-y divide-slate-50'>
                  {(fc.recipe ?? []).map((line: any, i: number) => (
                    <tr key={i} className='hover:bg-slate-50'>
                      <td className='px-4 py-2.5 font-medium'>{line.ingredient}</td>
                      <td className='px-4 py-2.5 text-right'>{line.qty}</td>
                      <td className='px-4 py-2.5 text-slate-500'>{line.unit}</td>
                      <td className='px-4 py-2.5 text-right text-slate-500'>${Number(line.line_cost ?? 0).toFixed(4)}</td>
                    </tr>
                  ))}
                  {(fc.recipe ?? []).length === 0 && (
                    <tr>
                      <td colSpan={4} className='px-4 py-4 text-slate-400 text-xs text-center'>
                        No recipe lines yet — add an ingredient below
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Add recipe line */}
            <div className='bg-white rounded-xl shadow-sm p-4'>
              <p className='text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3'>Add ingredient</p>
              <div className='flex gap-2 flex-wrap'>
                <select value={lineIngId}
                  onChange={e => {
                    setLineIngId(e.target.value)
                    const ing = (ingredients as any[])?.find((i: any) => i.id === e.target.value)
                    if (ing) setLineUnit(ing.unit)
                  }}
                  className='flex-1 min-w-36 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400'>
                  <option value=''>Select ingredient…</option>
                  {(ingredients as any[])?.map((i: any) => (
                    <option key={i.id} value={i.id}>{i.name} ({i.unit})</option>
                  ))}
                </select>
                <input type='number' step='0.001' placeholder='Qty' value={lineQty}
                  onChange={e => setLineQty(e.target.value)}
                  className='w-24 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400' />
                <input placeholder='Unit' value={lineUnit} onChange={e => setLineUnit(e.target.value)}
                  className='w-20 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400' />
                <button onClick={() => addLine.mutate()} disabled={!lineIngId || !lineQty || addLine.isPending}
                  className='bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold
                             hover:bg-blue-700 disabled:opacity-50'>
                  Add
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
