import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReviewerProvider } from '@/context/ReviewerContext'
import App from './App.jsx'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      // Do not retry client errors (404/409/422); retry transient failures once.
      retry: (count, error) => count < 1 && (!error?.response || error.response.status >= 500),
    },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ReviewerProvider>
          <App />
        </ReviewerProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
