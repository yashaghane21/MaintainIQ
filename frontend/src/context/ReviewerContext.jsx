import { createContext, useContext, useMemo, useState } from 'react'

const STORAGE_KEY = 'maintainiq.reviewer'
const DEFAULT_REVIEWER = 'Demo Technician'

const ReviewerContext = createContext({ reviewer: DEFAULT_REVIEWER, setReviewer: () => {} })

function readStored() {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_REVIEWER
  } catch {
    return DEFAULT_REVIEWER
  }
}

/**
 * Demo reviewer identity (there is no authentication in this MVP).
 * The name is sent with every edit/approve/reject and stored in the audit log.
 */
export function ReviewerProvider({ children, initialReviewer }) {
  const [reviewer, setReviewerState] = useState(() => initialReviewer || readStored())

  const value = useMemo(
    () => ({
      reviewer,
      setReviewer: (name) => {
        const next = name.trim() || DEFAULT_REVIEWER
        setReviewerState(next)
        try {
          localStorage.setItem(STORAGE_KEY, next)
        } catch {
          /* storage unavailable: keep in memory only */
        }
      },
    }),
    [reviewer],
  )
  return <ReviewerContext.Provider value={value}>{children}</ReviewerContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useReviewer = () => useContext(ReviewerContext)
