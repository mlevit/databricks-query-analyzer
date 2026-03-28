import { useState } from "react";
import type { TableInfo } from "../types";
import { humanBytes } from "../utils";

interface Props {
  tables: TableInfo[];
}

export default function TableAnalysis({ tables }: Props) {
  if (tables.length === 0) {
    return (
      <div className="panel table-analysis">
        <h2>Table Analysis</h2>
        <p className="table-analysis__empty">
          No table metadata available. The query may not reference any catalog tables,
          or DESCRIBE DETAIL was not able to retrieve information.
        </p>
      </div>
    );
  }

  return (
    <div className="panel table-analysis">
      <h2>Table Analysis</h2>
      <div className="table-analysis__list">
        {tables.map((t) => (
          <TableCard key={t.full_name} table={t} />
        ))}
      </div>
    </div>
  );
}

function TableCard({ table }: { table: TableInfo }) {
  const [expanded, setExpanded] = useState(false);
  const panelId = `table-detail-${table.full_name.replace(/[.\s]/g, "-")}`;

  return (
    <div className="table-card">
      <button
        className="table-card__header"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls={panelId}
      >
        <span className="table-card__name">{table.full_name}</span>
        <span className="table-card__meta">
          {table.format && <span className="badge badge--neutral">{table.format}</span>}
          {table.num_files != null && <span>{table.num_files.toLocaleString()} files</span>}
          {table.size_in_bytes != null && <span>{humanBytes(table.size_in_bytes)}</span>}
        </span>
        <span className={`table-card__chevron ${expanded ? "expanded" : ""}`}>&#9660;</span>
      </button>

      {expanded && (
        <div className="table-card__body" id={panelId}>
          <div className="table-card__detail">
            <strong>Clustering:</strong>{" "}
            {table.clustering_columns.length > 0
              ? table.clustering_columns.join(", ")
              : "None"}
          </div>
          <div className="table-card__detail">
            <strong>Partitioning:</strong>{" "}
            {table.partition_columns.length > 0
              ? table.partition_columns.join(", ")
              : "None"}
          </div>

          {table.recommendations.length > 0 && (
            <div className="table-card__recs">
              {table.recommendations.map((r, i) => (
                <div key={i} className={`rec-inline rec-inline--${r.severity}`}>
                  <span className="rec-inline__title">{r.title}</span>
                  <span className="rec-inline__desc">{r.description}</span>
                  {r.action && (
                    <code className="rec-inline__action">{r.action}</code>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
