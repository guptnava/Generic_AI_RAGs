import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import Veda from './Veda.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Veda />
  </StrictMode>,
)
