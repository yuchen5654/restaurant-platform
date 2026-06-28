import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { IngestionHub } from './pages/IngestionHub'
import { ReviewIngestion } from './pages/ReviewIngestion'
import { QuickSalesEntry } from './pages/QuickSalesEntry'
import { IngredientsPage } from './pages/IngredientsPage'
import { InventoryCount } from './pages/InventoryCount'
import { RecipeBuilder } from './pages/RecipeBuilder'
import { WasteLog } from './pages/WasteLog'
import { AskPage } from './pages/AskPage'

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
          <Route path='ingestion/review/:id' element={<ReviewIngestion />} />
          <Route path='sales/entry'          element={<QuickSalesEntry />} />
          <Route path='ingredients'          element={<IngredientsPage />} />
          <Route path='inventory/count'      element={<InventoryCount />} />
          <Route path='recipes'              element={<RecipeBuilder />} />
          <Route path='waste'                element={<WasteLog />} />
          <Route path='ask'                  element={<AskPage />} />
          <Route path='*'                    element={<Navigate to='/dashboard' replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
