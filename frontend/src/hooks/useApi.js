import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Custom hook to execute API calls with loading, error, and cancellation support.
 */
export function useApi(apiFn, deps = [], immediate = true) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);

  const abortControllerRef = useRef(null);

  const execute = useCallback(
    async (...args) => {
      // Abort previous request if still in flight
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setLoading(true);
      setError(null);

      try {
        const result = await apiFn(...args, controller.signal);
        setData(result);
        setLoading(false);
        return result;
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'An unexpected error occurred');
          setLoading(false);
        }
        return null;
      }
    },
    [apiFn]
  );

  useEffect(() => {
    if (immediate) {
      execute();
    }
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, deps);

  return { data, loading, error, execute, setData };
}
