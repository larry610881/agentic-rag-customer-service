import { renderHook, act } from '@testing-library/react';
import { usePagination } from './use-pagination';

describe('usePagination', () => {
  it('should start at page 1 with default page size 20', () => {
    const { result } = renderHook(() => usePagination());
    expect(result.current.page).toBe(1);
    expect(result.current.pageSize).toBe(20);
  });

  it('should update page when setPage called', () => {
    const { result } = renderHook(() => usePagination());
    act(() => result.current.setPage(3));
    expect(result.current.page).toBe(3);
  });

  it('should use custom defaultPageSize', () => {
    const { result } = renderHook(() => usePagination({ defaultPageSize: 10 }));
    expect(result.current.pageSize).toBe(10);
  });

  it('should update pageSize when setPageSize called', () => {
    const { result } = renderHook(() => usePagination());
    act(() => result.current.setPageSize(50));
    expect(result.current.pageSize).toBe(50);
  });
});
