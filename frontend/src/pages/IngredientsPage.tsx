import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

// ---- types ------------------------------------------------------------------

interface IngForm {
  name:                  string
  category:              string
  unit:                  string
  current_cost_per_unit: string
  par_level:             string
  reorder_qty:           string
  current_stock:         string
}

const BLANK: IngForm = {
  name: '', category: '', unit: '',
  current_cost_per_unit: '',
  par_level: '', reorder_qty: '', current_stock: '0',
}

function toPayload(f: IngForm) {
  return {
    name:                  f.name.trim(),
    category:              f.category.trim() || null,
    unit:                  f.unit.trim(),
    current_cost_per_unit: parseFloat(f.current_cost_per_unit) || 0,
    par_level:             f.par_level     !== '' ? parseFloat(f.par_level)     : null,
    reorder_qty:           f.reorder_qty   !== '' ? parseFloat(f.reorder_qty)   : null,
    current_stock:         f.current_stock !== '' ? parseFloat(f.current_stock) : 0,
  }
}

function ingToForm(ing: any): IngForm {
  return {
    name:                  ing.name,
    category:              ing.category ?? '',
    unit:                  ing.unit,
    current_cost_per_unit: String(Number(ing.current_cost_per_unit)),
    par_level:             ing.par_level   != null ? String(Number(ing.par_level))   : '',
    reorder_qty:           ing.reorder_qty != null ? String(Number(ing.reorder_qty)) : '',
    current_stock:         String(Number(ing.current_stock)),
  }
}

function isValid(f: IngForm) {
  return f.name.trim() !== '' && f.unit.trim() !== '' && f.current_cost_per_unit !== ''
}

// ---- sub-components ---------------------------------------------------------

const INPUT_CLS = 'border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full ' +
                  'focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100'

function FormRow({
  form, setForm, onSave, onCancel, saving, label,
}: {
  form:     IngForm
  setForm:  (f: IngForm) => void
  onSave:   () => void
  onCancel: () => void
  saving:   boolean
  label:    string
}) {
  const set = (k: keyof IngForm) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value })

  return (
    <div className='bg-blue-50 border border-blue-200 rounded-xl p-4 space-y-3'>
      <p className='text-xs font-semibold text-blue-700 uppercase tracking-wide'>{label}</p>
      <div className='grid grid-cols-2 md:grid-cols-4 gap-2'>
        <div className='col-span-2'>
          <label className='block text-xs text-slate-500 mb-0.5'>Name *</label>
          <input value={form.name} onChange={set('name')} placeholder='e.g. Chicken Breast'
            className={INPUT_CLS} />
        </div>
        <div>
          <label className='block text-xs text-slate-500 mb-0.5'>Category</label>
          <input value={form.category} onChange={set('category')} placeholder='e.g. Proteins'
            className={INPUT_CLS} />
        </div>
        <div>
          <label className='block text-xs text-slate-500 mb-0.5'>Unit *</label>
          <input value={form.unit} onChange={set('unit')} placeholder='lb / oz / each'
            className={INPUT_CLS} />
        </div>
        <div>
          <label className='block text-xs text-slate-500 mb-0.5'>Cost / unit *</label>
          <input type='number' step='0.0001' min='0' value={form.current_cost_per_unit}
            onChange={set('current_cost_per_unit')} placeholder='0.0000'
            className={INPUT_CLS} />
        </div>
        <div>
          <label className='block text-xs text-slate-500 mb-0.5'>Par level</label>
          <input type='number' step='0.001' min='0' value={form.par_level}
            onChange={set('par_level')} placeholder='—'
            className={INPUT_CLS} />
        </div>
        <div>
          <label className='block text-xs text-slate-500 mb-0.5'>Reorder qty</label>
          <input type='number' step='0.001' min='0' value={form.reorder_qty}
            onChange={set('reorder_qty')} placeholder='—'
            className={INPUT_CLS} />
        </div>
        <div>
          <label className='block text-xs text-slate-500 mb-0.5'>Current stock</label>
          <input type='number' step='0.001' min='0' value={form.current_stock}
            onChange={set('current_stock')} placeholder='0'
            className={INPUT_CLS} />
        </div>
      </div>
      <div className='flex gap-2 pt-1'>
        <button onClick={onSave} disabled={saving || !isValid(form)}
          className='bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm font-semibold
                     hover:bg-blue-700 disabled:opacity-50'>
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button onClick={onCancel}
          className='border border-slate-300 text-slate-600 px-4 py-1.5 rounded-lg text-sm hover:bg-slate-50'>
          Cancel
        </button>
      </div>
    </div>
  )
}

// ---- main page --------------------------------------------------------------

export function IngredientsPage() {
  const qc = useQueryClient()
  const [showNew,   setShowNew]   = useState(false)
  const [newForm,   setNewForm]   = useState<IngForm>(BLANK)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm,  setEditForm]  = useState<IngForm>(BLANK)
  const [search,    setSearch]    = useState('')

  const { data: ingredients, isLoading } = useQuery({
    queryKey: ['ingredients'],
    queryFn:  () => api.get('/ingredients/').then(r => r.data),
  })

  const create = useMutation({
    mutationFn: () => api.post('/ingredients/', toPayload(newForm)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ingredients'] })
      setNewForm(BLANK)
      setShowNew(false)
    },
  })

  const update = useMutation({
    mutationFn: (id: string) => api.patch(`/ingredients/${id}`, toPayload(editForm)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ingredients'] })
      setEditingId(null)
    },
  })

  function startEdit(ing: any) {
    setEditingId(ing.id)
    setEditForm(ingToForm(ing))
    setShowNew(false)
  }

  const filtered = ((ingredients as any[]) ?? []).filter((i: any) =>
    i.name.toLowerCase().includes(search.toLowerCase()) ||
    (i.category ?? '').toLowerCase().includes(search.toLowerCase()),
  )

  // Group by category for display
  const byCategory: Record<string, any[]> = {}
  for (const ing of filtered) {
    const cat = ing.category ?? 'Uncategorised'
    ;(byCategory[cat] ??= []).push(ing)
  }

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      {/* Header */}
      <div className='flex items-center justify-between mb-5'>
        <div>
          <h1 className='text-2xl font-bold text-slate-800'>Ingredients</h1>
          <p className='text-sm text-slate-500 mt-0.5'>
            {(ingredients as any[])?.length ?? 0} ingredient{(ingredients as any[])?.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => { setShowNew(v => !v); setEditingId(null) }}
          className='bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold
                     hover:bg-blue-700'
        >
          {showNew ? 'Cancel' : '+ Add Ingredient'}
        </button>
      </div>

      {/* New-ingredient form */}
      {showNew && (
        <div className='mb-5'>
          <FormRow
            form={newForm} setForm={setNewForm} label='New Ingredient'
            saving={create.isPending}
            onSave={() => create.mutate()}
            onCancel={() => { setShowNew(false); setNewForm(BLANK) }}
          />
          {create.isError && (
            <p className='text-red-500 text-xs mt-1'>Save failed — check required fields.</p>
          )}
        </div>
      )}

      {/* Search */}
      <div className='mb-4'>
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder='Filter by name or category…'
          className='border border-slate-300 rounded-lg px-3 py-2 text-sm w-full max-w-xs
                     focus:outline-none focus:border-blue-400'
        />
      </div>

      {isLoading && <p className='text-slate-400 text-sm'>Loading…</p>}

      {/* Ingredient list grouped by category */}
      {Object.entries(byCategory).map(([cat, items]) => (
        <div key={cat} className='mb-6'>
          <p className='text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2'>{cat}</p>
          <div className='bg-white rounded-xl shadow-sm overflow-hidden'>
            {/* Column headers */}
            <div className='hidden md:grid grid-cols-[1fr_80px_80px_80px_80px_80px_80px] gap-2
                            px-4 py-2 bg-slate-50 border-b border-slate-100
                            text-xs font-semibold text-slate-400 uppercase tracking-wide'>
              <span>Name</span>
              <span>Unit</span>
              <span className='text-right'>Cost/unit</span>
              <span className='text-right'>Par</span>
              <span className='text-right'>Reorder</span>
              <span className='text-right'>Stock</span>
              <span />
            </div>

            <ul className='divide-y divide-slate-50'>
              {items.map((ing: any) => (
                <li key={ing.id}>
                  {editingId === ing.id ? (
                    /* ---- edit form ---- */
                    <div className='p-4'>
                      <FormRow
                        form={editForm} setForm={setEditForm} label={`Editing: ${ing.name}`}
                        saving={update.isPending}
                        onSave={() => update.mutate(ing.id)}
                        onCancel={() => setEditingId(null)}
                      />
                      {update.isError && (
                        <p className='text-red-500 text-xs mt-1'>Save failed.</p>
                      )}
                    </div>
                  ) : (
                    /* ---- display row ---- */
                    <div className='grid grid-cols-[1fr_auto] md:grid-cols-[1fr_80px_80px_80px_80px_80px_80px]
                                    gap-2 px-4 py-3 items-center hover:bg-slate-50 transition-colors'>
                      <span className='font-medium text-slate-700 text-sm'>{ing.name}</span>
                      <span className='text-sm text-slate-500'>{ing.unit}</span>
                      <span className='text-sm text-slate-700 text-right'>
                        ${Number(ing.current_cost_per_unit).toFixed(4)}
                      </span>
                      <span className='text-sm text-slate-500 text-right'>
                        {ing.par_level != null ? Number(ing.par_level).toFixed(2) : '—'}
                      </span>
                      <span className='text-sm text-slate-500 text-right'>
                        {ing.reorder_qty != null ? Number(ing.reorder_qty).toFixed(2) : '—'}
                      </span>
                      <span className={`text-sm font-medium text-right ${
                        ing.par_level != null && Number(ing.current_stock) <= Number(ing.par_level)
                          ? 'text-yellow-600'
                          : 'text-slate-700'
                      }`}>
                        {Number(ing.current_stock).toFixed(2)}
                      </span>
                      <div className='flex justify-end'>
                        <button
                          onClick={() => startEdit(ing)}
                          className='text-xs text-blue-600 hover:text-blue-800 font-semibold px-2 py-1
                                     rounded hover:bg-blue-50'
                        >
                          Edit
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ))}

      {!isLoading && filtered.length === 0 && (
        <div className='bg-white rounded-xl p-10 text-center shadow-sm'>
          <p className='text-slate-400 text-sm'>
            {search ? 'No ingredients match your search.' : 'No ingredients yet — add your first one above.'}
          </p>
        </div>
      )}
    </div>
  )
}
