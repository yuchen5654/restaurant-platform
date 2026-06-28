interface KpiCardProps {
  label:   string
  value:   string
  target?: string
  alert?:  boolean
}

export function KpiCard({ label, value, target, alert }: KpiCardProps) {
  return (
    <div className={`bg-white rounded-xl border-l-4 p-5 shadow-sm ${alert ? 'border-red-500' : 'border-blue-300'}`}>
      <p className='text-xs text-slate-500 font-semibold uppercase tracking-widest'>{label}</p>
      <p className={`text-3xl font-bold mt-1 ${alert ? 'text-red-600' : 'text-slate-800'}`}>{value}</p>
      {target && <p className='text-xs text-slate-400 mt-1'>Target: {target}</p>}
    </div>
  )
}
