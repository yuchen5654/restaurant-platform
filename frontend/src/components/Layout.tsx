import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/dashboard',       label: 'Dashboard' },
  { to: '/sales/entry',     label: 'Sales Entry' },
  { to: '/ingestion',       label: 'Ingestion' },
  { to: '/ingredients',     label: 'Ingredients' },
  { to: '/inventory/count', label: 'Inventory Count' },
  { to: '/recipes',         label: 'Recipe Builder' },
  { to: '/waste',           label: 'Waste Log' },
]

export function Layout() {
  return (
    <div className='flex h-screen bg-slate-50'>
      <nav className='w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col'>
        <div className='px-5 py-4 border-b border-slate-100'>
          <p className='font-bold text-slate-800 text-sm leading-tight'>Restaurant<br />Platform</p>
        </div>
        <ul className='flex-1 py-3 px-2 space-y-0.5 overflow-auto'>
          {NAV.map(({ to, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  `block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'
                  }`
                }
              >
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className='p-4 border-t border-slate-100'>
          <button
            onClick={() => { localStorage.removeItem('access_token'); window.location.href = '/login' }}
            className='text-xs text-slate-400 hover:text-slate-600 w-full text-left'
          >
            Sign out
          </button>
        </div>
      </nav>
      <main className='flex-1 overflow-auto'>
        <Outlet />
      </main>
    </div>
  )
}
