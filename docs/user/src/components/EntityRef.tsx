import React from 'react';

interface EntityRefProps {
  /** Primary translation_key / entity ID suffix */
  id: string;
  /** Optional second key (for paired sensors like best/peak) */
  also?: string;
  /** Render without <strong> wrapper (default: false → bold) */
  noStrong?: boolean;
  /** Display name shown to the user */
  children: React.ReactNode;
}

/**
 * Compact inline reference to an entity, linking to the multi-language
 * sensor reference table.
 *
 * Uses a relative URL so links stay within the current docs version
 * (e.g. /next/, /v0.30.0/, or the latest version).
 *
 * Usage:
 *   <EntityRef id="average_price_today">Average Price Today</EntityRef>
 *   <EntityRef id="best_price_end_time" also="peak_price_end_time">End Time</EntityRef>
 */
export default function EntityRef({
  id,
  also,
  noStrong,
  children,
}: EntityRefProps): React.ReactElement {
  // Relative URL — browser resolves it relative to the current page,
  // which automatically preserves the versioned docs path prefix.
  const refUrl = `sensor-reference#ref-${id}`;
  const keys = also ? `${id} / ${also}` : id;
  const tooltip = `${keys} — View in all languages`;
  const content = noStrong ? children : <strong>{children}</strong>;

  return (
    <a
      href={refUrl}
      className="entity-ref"
      title={tooltip}
      aria-label={`Entity reference: ${keys}`}
    >
      {content}
    </a>
  );
}
