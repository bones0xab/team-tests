import React from "react";

interface Props {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

const PaginationControls: React.FC<Props> = ({
  page,
  pageSize,
  total,
  onPageChange,
}) => {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const goTo = (p: number) => {
    if (p < 1 || p > totalPages) return;
    onPageChange(p);
  };

  const buildPages = () => {
    const pages: number[] = [];
    const windowSize = 2;

    const start = Math.max(1, page - windowSize);
    const end = Math.min(totalPages, page + windowSize);

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    return pages;
  };

  const pages = buildPages();
  const startIndex = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, total);

  return (
    <div className="pagination-bar">
      <div className="pagination-info">
        Showing {startIndex}-{endIndex} of {total}
      </div>

      <div className="pagination-controls">
        <button
          className="pagination-btn"
          disabled={page === 1}
          onClick={() => goTo(1)}
          aria-label="First page"
        >
          {'<<'}
        </button>

        <button
          className="pagination-btn"
          disabled={page === 1}
          onClick={() => goTo(page - 1)}
          aria-label="Previous page"
        >
          {'<'}
        </button>

        {pages.map((p) => (
          <button
            key={p}
            onClick={() => goTo(p)}
            className={`pagination-btn${p === page ? " active" : ""}`}
            aria-label={`Go to page ${p}`}
            aria-current={p === page ? "page" : undefined}
          >
            {p}
          </button>
        ))}

        <button
          className="pagination-btn"
          disabled={page === totalPages}
          onClick={() => goTo(page + 1)}
          aria-label="Next page"
        >
          {'>'}
        </button>

        <button
          className="pagination-btn"
          disabled={page === totalPages}
          onClick={() => goTo(totalPages)}
          aria-label="Last page"
        >
          {'>>'}
        </button>
      </div>
    </div>
  );
};

export default PaginationControls;
