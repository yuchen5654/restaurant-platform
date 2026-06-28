import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { IngestionHub } from './pages/IngestionHub'
import { InventoryCount } from './pages/InventoryCount'
import { RecipeBuilder } from './pages/RecipeBuilder'
import { WasteLog } from './pages/WasteLog'

function RequireAuth({ children }: { children: React.ReactElement }) {
  return localStorage.getItem('access_token') ? children : <Navigate to='/login' replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path='/login' element={<Login />} />
        <Route path='/' element={<RequireAuth><Layout /></RequireAuth>}>
          <Route index element={<Navigate to='/dashboard' replace />} />
          <Route path='dashboard'            element={<Dashboard />} />
          <Route path='ingestion'            element={<IngestionHub />} />
          <Route path='ingestion/review/:id' element={<ComingSoon label='Review Ingestion' />} />
          <Route path='sales/entry'          element={<ComingSoon label='Quick Sales Entry' />} />
          <Route path='inventory/count'      element={<InventoryCount />} />
          <Route path='recipes'              element={<RecipeBuilder />} />
          <Route path='waste'                element={<WasteLog />} />
          <Route path='*'                    element={<Navigate to='/dashboard' replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

function ComingSoon({ label }: { label: string }) {
  return (
    <div className='p-8 text-slate-400 text-sm'>
      <p className='font-semibold text-slate-600 mb-1'>{label}</p>
      <p>Built in Step 5B Part 2 — coming next session.</p>
    </div>
  )
}
