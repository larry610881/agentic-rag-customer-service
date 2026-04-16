import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import type { ReactElement } from 'react';
import { PageBreadcrumb } from './page-breadcrumb';

function renderWithRouter(ui: ReactElement, initialEntries = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="*" element={ui} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('PageBreadcrumb', () => {
  it('renders all items and marks the last as current page', () => {
    renderWithRouter(
      <PageBreadcrumb
        items={[
          { label: '知識庫', to: '/knowledge' },
          { label: 'carrefour', to: '/knowledge/1' },
          { label: '家樂福4月DM' },
        ]}
      />,
    );

    expect(screen.getByRole('navigation', { name: 'breadcrumb' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '知識庫' })).toHaveAttribute('href', '/knowledge');
    expect(screen.getByRole('link', { name: 'carrefour' })).toHaveAttribute('href', '/knowledge/1');

    const current = screen.getByText('家樂福4月DM');
    expect(current).toHaveAttribute('aria-current', 'page');
  });

  it('renders onClick item as button and invokes handler', async () => {
    const user = userEvent.setup();
    const collapse = vi.fn();
    renderWithRouter(
      <PageBreadcrumb
        items={[
          { label: '運行列表', to: '/admin/prompt-optimizer/runs' },
          { label: 'Run #42', onClick: collapse },
          { label: '第 3 輪迭代' },
        ]}
      />,
    );

    const btn = screen.getByRole('button', { name: 'Run #42' });
    await user.click(btn);
    expect(collapse).toHaveBeenCalledTimes(1);
  });

  it('truncates long labels and exposes original via title', () => {
    const longLabel = '這是一個非常非常非常長的文件名稱用來測試截斷行為';
    renderWithRouter(
      <PageBreadcrumb
        items={[
          { label: '知識庫', to: '/knowledge' },
          { label: longLabel },
        ]}
        maxLabelLength={10}
      />,
    );

    const current = screen.getByTitle(longLabel);
    expect(current.textContent).toMatch(/\.\.\.$/);
    expect(current.textContent!.length).toBeLessThan(longLabel.length);
  });

  it('returns null for empty items array', () => {
    const { container } = renderWithRouter(<PageBreadcrumb items={[]} />);
    expect(container.querySelector('nav')).toBeNull();
  });

  it('collapses middle segments with ellipsis when more than 3 items', () => {
    renderWithRouter(
      <PageBreadcrumb
        items={[
          { label: '提示詞優化器', to: '/admin/prompt-optimizer' },
          { label: '運行列表', to: '/admin/prompt-optimizer/runs' },
          { label: 'Run #42', to: '/admin/prompt-optimizer/runs/42' },
          { label: '第 3 輪迭代' },
        ]}
      />,
    );

    // First, last, and second-to-last (parent of current) are always visible
    expect(screen.getByRole('link', { name: '提示詞優化器' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Run #42' })).toBeInTheDocument();
    expect(screen.getByText('第 3 輪迭代')).toBeInTheDocument();

    // Middle segment "運行列表" is collapsed into ellipsis on small screens
    // (element still in DOM but hidden via Tailwind responsive classes — check via sr-only "More")
    expect(screen.getByText('More')).toBeInTheDocument();
  });

  it('renders non-last item with no `to` and no `onClick` as plain text', () => {
    renderWithRouter(
      <PageBreadcrumb
        items={[
          { label: 'Root', to: '/' },
          { label: 'Passive Label' },
          { label: 'Current' },
        ]}
      />,
    );

    const passive = screen.getByText('Passive Label');
    expect(passive.tagName).not.toBe('A');
    expect(passive.tagName).not.toBe('BUTTON');
    expect(passive).not.toHaveAttribute('aria-current');
  });
});
