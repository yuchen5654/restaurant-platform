import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Link } from 'react-router-dom'
import api from '../api/client'

const TYPE_LABEL: Record<string, string> = {
  csv:         'CSV Import',
  ocr_invoice: 'Invoice Photo',
  ocr_count:   'Count Photo',
  voice:       'Voice Count',
  email:       'Email',
}

const IMPORT_COLOR: Record<string, string> = {
  invoice:         'bg-purple-50 text-purple-700',
  inventory_count: 'bg-blue-50 text-blue-700',
  sales:           'bg-green-50 text-green-700',
  labor:           'bg-orange-50 text-orange-700',
}

export function IngestionHub() {
  const { data: staged, isLoading, refetch } = useQuery({
    queryKey: ['staged'],
    queryFn:  () => api.get('/ingestion/staged', { params: { status: 'pending' } }).then(r => r.data),
    refetchInterval: 30_000,
  })

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <div className='flex justify-between items-center mb-6'>
        <h1 className='text-2xl font-bold text-slate-800'>Ingestion Hub</h1>
        <button onClick={() => refetch()} className='text-xs text-slate-400 hover:text-slate-600'>Refresh</button>
      </div>

      {/* Upload entry points */}
      <div className='grid grid-cols-2 md:grid-cols-4 gap-3 mb-8'>
        {[
          { label: 'Upload CSV',  sub: 'Sales, inventory or invoice',  icon: '📄', to: '/ingestion/csv'   },
          { label: 'Photo / OCR', sub: 'Invoice or count sheet photo', icon: '📷', to: '/ingestion/photo' },
          { label: 'Voice Count', sub: 'Speak your inventory count',   icon: '🎙',  to: '/ingestion/voice' },
          { label: 'Sales Entry', sub: 'End-of-day item counts',       icon: '✏️', to: '/sales/entry'     },
        ].map(b => (
          <Link key={b.label} to={b.to}
            className='bg-white border border-slate-200 rounded-xl p-4 hover:border-blue-300 hover:shadow-sm transition-all'>
            <span className='text-2xl block mb-1'>{b.icon}</span>
            <p className='font-semibold text-slate-800 text-sm'>{b.label}</p>
            <p className='text-xs text-slate-400 mt-0.5'>{b.sub}</p>
          </Link>
        ))}
      </div>

      {/* Pending staged records */}
      <div className='bg-white rounded-xl shadow-sm'>
        <div className='px-5 py-4 border-b border-slate-100 flex items-center gap-2'>
          <h2 className='font-semibold text-slate-700'>Pending Review</h2>
          {staged && (
            <span className='text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full font-semibold'>
              {(staged as any[]).length}
            </span>
          )}
        </div>

        {isLoading && <p className='p-5 text-sm text-slate-400'>Loading…</p>}

        {!isLoading && (staged as any[])?.length === 0 && (
          <p className='p-6 text-sm text-slate-400 text-center'>All caught up — no pending items.</p>
        )}

        <ul className='divide-y divide-slate-50'>
          {(staged as any[])?.map((item: any) => (
            <li key={item.id} className='flex items-center justify-between px-5 py-3 hover:bg-slate-50'>
              <div className='flex items-center gap-3'>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${IMPORT_COLOR[item.import_type] ?? 'bg-slate-100 text-slate-600'}`}>
                  {item.import_type.replace('_', ' ')}
                </span>
                <div>
                  <p className='text-sm font-medium text-slate-700'>
                    {TYPE_LABEL[item.ingestion_type] ?? item.ingestion_type}
                  </p>
                  <p className='text-xs text-slate-400'>
                    {format(new Date(item.created_at), 'MMM d, yyyy h:mm a')}
                  </p>
                </div>
              </div>
              <Link to={`/ingestion/review/${item.id}`}
                className='text-sm font-semibold text-blue-600 hover:text-blue-800'>
                Review →
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
