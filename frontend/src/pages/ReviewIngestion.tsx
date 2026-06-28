import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

const confColor = (score: number) =>
  score > 0.85 ? 'border-green-300 bg-green-50' :
  score > 0.60 ? 'border-yellow-300 bg-yellow-50' :
                 'border-red-300 bg-red-50'

export function ReviewIngestion() {
  const { id: stagedId } = useParams<{ id: string }>()
  const navigate         = useNavigate()
  const qc               = useQueryClient()

  const { data: staged, isLoading } = useQuery({
    queryKey: ['staged', stagedId],
    queryFn:  () => api.get(`/ingestion/staged/${stagedId}`).then(r => r.data),
    enabled:  !!stagedId,
  })

  const [edits, setEdits] = useState<any>(null)

  // Fix: extracted_data comes back as a parsed object from the JSON column —
  // no JSON.parse() needed (the step file assumed it was stored as a string).
  const raw  = staged?.extracted_data ?? null
  const data = edits ?? raw

  const confirm = useMutation({
    mutationFn: () =>
      api.post(`/ingestion/staged/${stagedId}/confirm`, {
        // Only send corrected_data when the operator actually edited something.
        corrected_data: edits ?? undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staged'] })
      navigate('/ingestion')
    },
  })

  const reject = useMutation({
    mutationFn: () => api.post(`/ingestion/staged/${stagedId}/reject`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staged'] })
      navigate('/ingestion')
    },
  })

  if (isLoading) {
    return <div className='p-6 text-slate-400 text-sm'>Loading…</div>
  }
  if (!staged || !data) {
    return (
      <div className='p-6'>
        <p className='text-red-500 text-sm'>Staged record not found.</p>
        <button onClick={() => navigate('/ingestion')}
          className='mt-2 text-sm text-blue-600 hover:underline'>← Back to Ingestion Hub</button>
      </div>
    )
  }

  const isInvoice = staged.import_type === 'invoice'
  const itemsKey  = isInvoice ? 'line_items' : 'items'
  const items: any[] = data[itemsKey] ?? []

  function updateItem(i: number, field: string, value: any) {
    const updated = [...items]
    updated[i] = { ...updated[i], [field]: value }
    setEdits((p: any) => ({ ...(p ?? raw), [itemsKey]: updated }))
  }

  const busy = confirm.isPending || reject.isPending

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <div className='max-w-2xl mx-auto'>

        {/* Header */}
        <div className='flex items-start gap-3 mb-5'>
          <button onClick={() => navigate('/ingestion')}
            className='mt-0.5 text-slate-400 hover:text-slate-600 text-sm shrink-0'>
            ←
          </button>
          <div>
            <h1 className='text-lg font-bold text-slate-800'>
              Review {isInvoice ? 'Invoice' : 'Inventory Count'}
            </h1>
            <p className='text-xs text-slate-400 mt-0.5 capitalize'>
              via {staged.ingestion_type.replace(/_/g, ' ')}
              {edits && <span className='ml-2 text-blue-500'>· edited</span>}
            </p>
          </div>
        </div>

        {/* Invoice header fields */}
        {isInvoice && (
          <div className='grid grid-cols-2 gap-3 mb-4 p-4 bg-white rounded-xl shadow-sm'>
            <div>
              <label className='text-xs font-semibold text-slate-500 block mb-1'>Vendor</label>
              <input
                value={data.vendor_name ?? ''}
                placeholder='Vendor name'
                className='w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm
                           focus:outline-none focus:border-blue-400'
                onChange={e => setEdits((p: any) => ({ ...(p ?? raw), vendor_name: e.target.value }))}
              />
            </div>
            <div>
              <label className='text-xs font-semibold text-slate-500 block mb-1'>Invoice #</label>
              <input
                value={data.invoice_number ?? ''}
                placeholder='Optional'
                className='w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm
                           focus:outline-none focus:border-blue-400'
                onChange={e => setEdits((p: any) => ({ ...(p ?? raw), invoice_number: e.target.value }))}
              />
            </div>
          </div>
        )}

        {/* Line items */}
        <div className='space-y-2 mb-5'>
          {items.map((item: any, i: number) => (
            <div key={i} className={`border rounded-lg p-3 ${confColor(item.confidence ?? 0.9)}`}>
              <div className='flex gap-2 items-center flex-wrap'>
                <input
                  value={item.ingredient_name ?? ''}
                  placeholder='Ingredient name'
                  className='flex-1 min-w-32 bg-transparent border-b border-transparent
                             focus:border-slate-400 outline-none text-sm font-medium'
                  onChange={e => updateItem(i, 'ingredient_name', e.target.value)}
                />
                <input
                  type='number' value={item.quantity ?? ''} placeholder='Qty'
                  className='w-16 text-center border rounded-lg px-1.5 py-0.5 text-sm
                             focus:outline-none focus:border-blue-400'
                  onChange={e => updateItem(i, 'quantity', parseFloat(e.target.value))}
                />
                <input
                  value={item.unit ?? ''} placeholder='unit'
                  className='w-16 text-center border rounded-lg px-1.5 py-0.5 text-sm
                             focus:outline-none focus:border-blue-400'
                  onChange={e => updateItem(i, 'unit', e.target.value)}
                />
                {isInvoice && (
                  <input
                    type='number' step='0.01' value={item.unit_cost ?? ''} placeholder='$/unit'
                    className='w-20 text-right border rounded-lg px-1.5 py-0.5 text-sm
                               focus:outline-none focus:border-blue-400'
                    onChange={e => updateItem(i, 'unit_cost', parseFloat(e.target.value))}
                  />
                )}
              </div>
              {(item.confidence ?? 1) < 0.7 && (
                <p className='text-xs text-yellow-700 mt-1.5'>Low confidence — please verify</p>
              )}
            </div>
          ))}

          {items.length === 0 && (
            <p className='text-sm text-slate-400 text-center py-6 bg-white rounded-xl'>
              No items extracted
            </p>
          )}
        </div>

        {/* Voice transcript (collapsible) */}
        {staged.raw_input && staged.ingestion_type === 'voice' && (
          <details className='mb-5 text-xs text-slate-500'>
            <summary className='cursor-pointer hover:text-slate-700 font-medium'>
              View transcript
            </summary>
            <p className='mt-2 p-3 bg-white rounded-lg leading-relaxed'>{staged.raw_input}</p>
          </details>
        )}

        {/* Error message */}
        {(confirm.isError || reject.isError) && (
          <div className='mb-4 bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded-lg'>
            Something went wrong — try again or contact support.
          </div>
        )}

        {/* Actions */}
        <div className='flex gap-3'>
          <button
            onClick={() => confirm.mutate()}
            disabled={busy}
            className='flex-1 bg-blue-600 text-white py-2.5 rounded-lg font-semibold
                       hover:bg-blue-700 disabled:opacity-50 transition-opacity'
          >
            {confirm.isPending ? 'Saving…' : 'Confirm & Save'}
          </button>
          <button
            onClick={() => reject.mutate()}
            disabled={busy}
            className='px-6 border border-red-200 text-red-500 py-2.5 rounded-lg
                       hover:bg-red-50 disabled:opacity-50 transition-opacity'
          >
            {reject.isPending ? '…' : 'Reject'}
          </button>
        </div>

      </div>
    </div>
  )
}
