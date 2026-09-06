interface PaginationProps {
  currentPage: number;
  totalPages: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

export function Pagination({ currentPage, totalPages, pageSize, onPageChange, onPageSizeChange }: PaginationProps) {
  return (
    <div className="filter-bar" style={{ marginTop: 20, marginBottom: 0 }} aria-label="Pagination">
      <button type="button" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage <= 1}>
        Précédent
      </button>
      <span style={{ color: 'var(--color-muted-foreground)', fontSize: 14, fontWeight: 500 }}>
        Page {currentPage} sur {totalPages}
      </span>
      <button type="button" onClick={() => onPageChange(currentPage + 1)} disabled={currentPage >= totalPages}>
        Suivant
      </button>
      <span className="filter-count" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        Afficher
        <select
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
          style={{ width: 'auto', minWidth: 80 }}
          aria-label="Résultats par page"
        >
          <option value={10}>10</option>
          <option value={25}>25</option>
          <option value={50}>50</option>
        </select>
      </span>
    </div>
  );
}
