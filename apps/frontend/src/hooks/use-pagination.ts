import { useEffect, useState } from 'react';

interface UsePaginationOptions {
  defaultPageSize?: number;
  /**
   * M46：目前資料的總頁數。傳入後，當 page 超出（例如在最末頁刪光資料使 total_pages
   * 縮小）自動夾回最後一頁，避免使用者被困在空的幽靈頁、且 PaginationControls 因
   * totalPages<=1 消失而無 UI 可回到第 1 頁。未傳入則維持原行為（不夾）。
   */
  totalPages?: number;
}

export function usePagination({
  defaultPageSize = 20,
  totalPages,
}: UsePaginationOptions = {}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);

  useEffect(() => {
    if (totalPages !== undefined && totalPages >= 1 && page > totalPages) {
      setPage(totalPages);
    }
  }, [totalPages, page]);

  return { page, setPage, pageSize, setPageSize };
}
