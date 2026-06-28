# Step 7 — React Frontend (Dashboard & Entry Forms)

**Estimated time:** 12–16 hours
**Phase:** 1 (Foundation)
**Depends on:** Steps 4, 5B, 6.

---

## Goal

The operator-facing interface: daily dashboard with KPI cards and item profitability, recipe builder, ingestion hub (pending staged records), waste logging, manual sales entry.

## 7.1 Setup

```bash
cd frontend
npx create-react-app . --template typescript
npm install recharts axios @tanstack/react-query date-fns react-router-dom
npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p
```

## 7.2 API client — `src/api/client.ts`

```tsx
import axios from 'axios';
const api = axios.create({ baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000' });
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
api.interceptors.response.use(
  r => r,
  err => { if (err.response?.status===401) window.location.href='/login'; return Promise.reject(err); }
);
export default api;
```

## 7.3 KpiCard — `src/components/KpiCard.tsx`

```tsx
interface KpiCardProps { label:string; value:string; target?:string; alert?:boolean; }
export function KpiCard({ label, value, target, alert }: KpiCardProps) {
  return (
    <div className={`bg-white rounded-xl border-l-4 p-5 shadow-sm
                     ${alert ? 'border-red-500' : 'border-blue-300'}`}>
      <p className='text-xs text-slate-500 font-semibold uppercase tracking-widest'>{label}</p>
      <p className={`text-3xl font-bold mt-1 ${alert ? 'text-red-600':'text-slate-800'}`}>{value}</p>
      {target && <p className='text-xs text-slate-400 mt-1'>Target: {target}</p>}
    </div>
  );
}
```

## 7.4 Dashboard — `src/pages/Dashboard.tsx`

```tsx
import { useQuery } from '@tanstack/react-query';
import { KpiCard } from '../components/KpiCard';
import api from '../api/client';
import { subDays } from 'date-fns';

export function Dashboard() {
  const today    = new Date();
  const month30  = subDays(today, 30).toISOString();
  const todayISO = today.toISOString();

  const { data: fc30 } = useQuery({
    queryKey: ['food-cost','30d'],
    queryFn:  ()=>api.get('/sales/food-cost',{params:{date_from:month30,date_to:todayISO}}).then(r=>r.data),
  });
  const { data: items } = useQuery({
    queryKey: ['profitability','30d'],
    queryFn:  ()=>api.get('/sales/item-profitability',{params:{date_from:month30,date_to:todayISO,limit:10}}).then(r=>r.data),
  });
  const fcAlert = fc30?.food_cost_pct && fc30.food_cost_pct > 35;

  return (
    <div className='p-6 bg-slate-50 min-h-screen'>
      <h1 className='text-2xl font-bold text-slate-800 mb-6'>Operations Dashboard</h1>
      <div className='grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8'>
        <KpiCard label='Food Cost % (30d)'
                 value={fc30?.food_cost_pct ? `${fc30.food_cost_pct}%` : '—'}
                 target='30%' alert={fcAlert} />
        <KpiCard label='Net Revenue (30d)'
                 value={fc30?.total_revenue ? `$${fc30.total_revenue.toLocaleString()}`:'—'} />
      </div>
      {items && (
        <div className='bg-white rounded-xl p-5 shadow-sm'>
          <h2 className='font-semibold text-slate-700 mb-4'>Menu Item Profitability (30 days)</h2>
          <table className='w-full text-sm'>
            <thead><tr className='text-left text-slate-400 border-b text-xs uppercase tracking-wide'>
              <th className='pb-2'>Item</th><th>Qty</th><th>Revenue</th><th>FC%</th><th>Gross Profit</th>
            </tr></thead>
            <tbody>
              {items.map((item:any,i:number)=>(
                <tr key={i} className='border-b border-slate-50 hover:bg-slate-50'>
                  <td className='py-2 font-medium'>{item.menu_item_id}</td>
                  <td>{item.quantity_sold}</td>
                  <td>${item.revenue?.toFixed(2)}</td>
                  <td className={item.food_cost_pct>35?'text-red-500 font-bold':'text-green-600'}>
                    {item.food_cost_pct}%</td>
                  <td>${item.gross_profit?.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

## 7.5 Pages to build

- `/dashboard` → above
- `/sales/entry` → `QuickSalesEntry.tsx` (built in Step 5B Part 2)
- `/ingestion` → **Ingestion hub**: upload buttons (CSV/photo/voice) + list of pending staged records, each with a Review button
- `/ingestion/review/:id` → `ReviewIngestion.tsx` (built in Step 5B Part 2)
- `/inventory/count` → mobile count list (ingredient list + actual qty fields, shows variance)
- `/recipes` → recipe builder (two-column: menu item list + recipe line editor)
- `/waste` → quick waste log form with floating action button

## Done when
Dashboard shows live food cost % and profitability. Ingestion hub lists pending staged records and links to the review screen.

## Then
Update checkbox, `git commit`. Phase 1 complete. Move to `step-08-forecasting.md` (Phase 2) when you have 60+ days of live data.
