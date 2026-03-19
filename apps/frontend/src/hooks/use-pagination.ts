import { useState } from 'react';

interface UsePaginationOptions {
  defaultPageSize?: number;
}

export function usePagination({ defaultPageSize = 20 }: UsePaginationOptions = {}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);

  return { page, setPage, pageSize, setPageSize };
}
