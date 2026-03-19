import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PaginationControls } from './pagination-controls';

describe('PaginationControls', () => {
  it('should render page info with total', () => {
    render(
      <PaginationControls page={2} totalPages={5} onPageChange={() => {}} />,
    );
    expect(screen.getByText('2 / 5')).toBeInTheDocument();
  });

  it('should disable prev button on first page', () => {
    render(
      <PaginationControls page={1} totalPages={5} onPageChange={() => {}} />,
    );
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
  });

  it('should disable next button on last page', () => {
    render(
      <PaginationControls page={5} totalPages={5} onPageChange={() => {}} />,
    );
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled();
  });

  it('should call onPageChange when clicking next', async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(
      <PaginationControls page={2} totalPages={5} onPageChange={onPageChange} />,
    );
    await user.click(screen.getByRole('button', { name: /next/i }));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it('should call onPageChange when clicking prev', async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(
      <PaginationControls page={3} totalPages={5} onPageChange={onPageChange} />,
    );
    await user.click(screen.getByRole('button', { name: /previous/i }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('should return null when totalPages is 1', () => {
    const { container } = render(
      <PaginationControls page={1} totalPages={1} onPageChange={() => {}} />,
    );
    expect(container.innerHTML).toBe('');
  });
});
