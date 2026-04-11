import React, {useCallback, useEffect, useRef, useState} from 'react';

interface RowEntry {
  /** The entity-anchor id (e.g. "ref-current_interval_price") */
  anchorId: string;
  /** The translation_key / entity ID suffix */
  key: string;
  /** English name (first translated name) */
  englishName: string;
  /** All translated names (for display in results) */
  translatedNames: string[];
  /** All searchable text from the row (names in all languages, key) */
  searchText: string;
  /** The <tr> element */
  row: HTMLTableRowElement;
  /** Platform heading (e.g. "Sensors", "Binary Sensors") */
  platform: string;
  /** Doc page slugs that reference this entity (from data-refs attribute) */
  docRefs: string[];
  /** Name cells (columns between key and default) for match highlighting */
  nameCells: HTMLTableCellElement[];
  /** Original innerHTML of name cells (for restoring after highlighting) */
  originalNameHTML: string[];
}

const MAX_RESULTS = 12;

/** Display names for doc page back-links (from data-refs attribute). */
const DOC_NAMES: Record<string, string> = {
  sensors: 'Sensors Guide',
  configuration: 'Configuration',
  'period-calculation': 'Period Calculation',
  'automation-examples': 'Automation Examples',
  actions: 'Actions',
};

/** Platform filter chips. `match` is tested with startsWith against h2 text. */
const PLATFORM_CHIPS = [
  {label: 'Sensors', match: 'Sensors'},
  {label: 'Binary Sensors', match: 'Binary Sensors'},
  {label: 'Numbers', match: 'Number Entities'},
  {label: 'Switches', match: 'Switch Entities'},
];

/**
 * Highlight `needle` inside `html` by wrapping matches in <mark> tags.
 * Only replaces inside text nodes (outside HTML tags) to keep markup intact.
 */
function highlightHTML(html: string, needle: string): string {
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`(${escaped})`, 'gi');
  return html.replace(/(<[^>]*>)|([^<]+)/g, (_m, tag: string, text: string) => {
    if (tag) return tag;
    return text.replace(re, '<mark class="entity-match">$1</mark>');
  });
}

/**
 * Live-filtering search bar for the sensor-reference page.
 *
 * Scans all `.entity-anchor` spans on mount to build an index of
 * entity keys and translated names. Typing filters the tables in
 * real-time and shows a clickable result list to jump to entries.
 */
export default function EntitySearch(): React.ReactElement {
  const [query, setQuery] = useState('');
  const [total, setTotal] = useState(0);
  const [matchCount, setMatchCount] = useState(0);
  const [matches, setMatches] = useState<RowEntry[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [activeChip, setActiveChip] = useState<string | null>(null);
  const entriesRef = useRef<RowEntry[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLUListElement>(null);

  // ── Build the search index on mount ──────────────────────────
  useEffect(() => {
    const anchors = document.querySelectorAll<HTMLSpanElement>('.entity-anchor');
    const entries: RowEntry[] = [];

    anchors.forEach((anchor) => {
      const row = anchor.closest('tr');
      if (!row) return;

      const anchorId = anchor.id;
      const key = anchorId.replace(/^ref-/, '');

      // Determine platform from closest h2 above this table
      let platform = '';
      const table = row.closest('table');
      if (table) {
        let el = table.previousElementSibling;
        while (el) {
          if (el.tagName === 'H2') {
            platform = el.textContent?.trim() ?? '';
            break;
          }
          el = el.previousElementSibling;
        }
      }

      // Doc back-links from data attribute (set by generator)
      const refsAttr = anchor.getAttribute('data-refs');
      const docRefs = refsAttr ? refsAttr.split(',').filter(Boolean) : [];

      // Collect text from all cells + store name cells for highlighting
      const cells = row.querySelectorAll('td');
      const texts: string[] = [key];
      const translatedNames: string[] = [];
      const nameCells: HTMLTableCellElement[] = [];
      const originalNameHTML: string[] = [];

      cells.forEach((cell, i) => {
        const text = cell.textContent?.trim();
        if (text && text !== '✅' && text !== '❌') {
          texts.push(text);
        }
        // Name cells = columns between key (0) and default (last)
        if (i > 0 && i < cells.length - 1) {
          nameCells.push(cell);
          originalNameHTML.push(cell.innerHTML);
          const t = cell.textContent?.trim();
          if (t) translatedNames.push(t);
        }
      });

      // ── Inject copy-entity-ID button ──
      const firstCell = cells[0];
      if (firstCell && !firstCell.querySelector('.entity-copy-btn')) {
        const btn = document.createElement('button');
        btn.className = 'entity-copy-btn';
        btn.title = 'Copy entity ID suffix';
        btn.setAttribute('aria-label', `Copy ${key}`);
        btn.textContent = '\u29C9'; // ⧉ overlapping squares
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          navigator.clipboard.writeText(key).then(() => {
            btn.textContent = '\u2713'; // ✓
            btn.classList.add('copied');
            setTimeout(() => {
              btn.textContent = '\u29C9';
              btn.classList.remove('copied');
            }, 1500);
          });
        });
        firstCell.appendChild(btn);
      }

      // ── Inject doc back-links ──
      if (docRefs.length > 0 && firstCell && !firstCell.querySelector('.entity-back-links')) {
        const span = document.createElement('span');
        span.className = 'entity-back-links';
        docRefs.forEach((slug) => {
          const a = document.createElement('a');
          a.href = slug;
          a.className = 'entity-back-link';
          a.title = DOC_NAMES[slug] ?? slug;
          a.setAttribute('aria-label', `View in: ${DOC_NAMES[slug] ?? slug}`);
          a.textContent = '\uD83D\uDCD6'; // 📖
          span.appendChild(a);
        });
        firstCell.appendChild(span);
      }

      entries.push({
        anchorId,
        key,
        englishName: translatedNames[0] ?? key,
        translatedNames,
        searchText: texts.join(' ').toLowerCase(),
        row,
        platform,
        docRefs,
        nameCells,
        originalNameHTML,
      });
    });

    entriesRef.current = entries;
    setTotal(entries.length);
    setMatchCount(entries.length);
  }, []);

  // ── Jump to #ref-* hash on arrival / hash change ─────────────
  useEffect(() => {
    const entries = entriesRef.current;
    if (entries.length === 0) return;

    const jumpToHash = () => {
      const hash = window.location.hash;
      if (!hash.startsWith('#ref-')) return;

      const key = hash.slice(5);
      const entry = entries.find((e) => e.key === key);
      if (!entry) return;

      document.querySelectorAll('.entity-search-jump-highlight').forEach((el) => {
        el.classList.remove('entity-search-jump-highlight');
      });
      const anchor = document.getElementById(entry.anchorId);
      if (anchor) {
        requestAnimationFrame(() => {
          anchor.scrollIntoView({behavior: 'smooth', block: 'center'});
          void entry.row.offsetWidth;
          entry.row.classList.add('entity-search-jump-highlight');
        });
      }
    };

    jumpToHash();
    window.addEventListener('hashchange', jumpToHash);
    return () => window.removeEventListener('hashchange', jumpToHash);
  }, [total]);

  // ── Global "/" shortcut to focus the search input ────────────
  useEffect(() => {
    const handleSlash = (e: KeyboardEvent) => {
      if (
        e.key === '/' &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement) &&
        !(e.target instanceof HTMLSelectElement)
      ) {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      }
    };
    document.addEventListener('keydown', handleSlash);
    return () => document.removeEventListener('keydown', handleSlash);
  }, []);

  // ── Core filtering logic ─────────────────────────────────────
  const applyFilter = useCallback((search: string, chip: string | null) => {
    const entries = entriesRef.current;
    const needle = search.toLowerCase().trim();
    let matchCountLocal = 0;
    const matchedEntries: RowEntry[] = [];
    const sectionsWithMatches = new Set<Element>();

    // Restore previous match highlights
    entries.forEach((entry) => {
      entry.nameCells.forEach((cell, i) => {
        if (cell.innerHTML !== entry.originalNameHTML[i]) {
          cell.innerHTML = entry.originalNameHTML[i];
        }
      });
    });

    entries.forEach((entry) => {
      // Platform chip filter
      const chipMatch = !chip || entry.platform.startsWith(chip);
      // Text search filter
      const textMatch = !needle || entry.searchText.includes(needle);
      const isMatch = chipMatch && textMatch;

      if (isMatch) {
        matchCountLocal++;
        matchedEntries.push(entry);
        entry.row.classList.remove('entity-search-hidden');
        entry.row.classList.add('entity-search-match');

        // Highlight matched text in name cells
        if (needle) {
          entry.nameCells.forEach((cell, i) => {
            cell.innerHTML = highlightHTML(entry.originalNameHTML[i], needle);
          });
        }

        const table = entry.row.closest('table');
        if (table) {
          let prev = table.previousElementSibling;
          while (prev && prev.tagName !== 'H3' && prev.tagName !== 'H2') {
            prev = prev.previousElementSibling;
          }
          if (prev) sectionsWithMatches.add(prev);
        }
      } else {
        entry.row.classList.add('entity-search-hidden');
        entry.row.classList.remove('entity-search-match');
      }
    });

    const isActive = !!(needle || chip);
    if (isActive) {
      document.querySelectorAll('.markdown h3, .markdown h2').forEach((heading) => {
        if (heading.textContent?.includes('How to Find')) return;
        const hasMatch = sectionsWithMatches.has(heading);

        if (heading.tagName === 'H3') {
          heading.classList.toggle('entity-search-section-hidden', !hasMatch);
          let el = heading.nextElementSibling;
          while (el && el.tagName !== 'TABLE' && el.tagName !== 'H3' && el.tagName !== 'H2') {
            el.classList.toggle('entity-search-section-hidden', !hasMatch);
            el = el.nextElementSibling;
          }
        }
      });
    } else {
      document.querySelectorAll('.entity-search-section-hidden').forEach((el) => {
        el.classList.remove('entity-search-section-hidden');
      });
    }

    setMatchCount(matchCountLocal);
    setMatches(isActive ? matchedEntries : []);
    setActiveIndex(-1);
  }, []);

  const scrollToEntry = useCallback((entry: RowEntry) => {
    document.querySelectorAll('.entity-search-jump-highlight').forEach((el) => {
      el.classList.remove('entity-search-jump-highlight');
    });

    const anchor = document.getElementById(entry.anchorId);
    if (anchor) {
      history.pushState(null, '', `#${entry.anchorId}`);
      anchor.scrollIntoView({behavior: 'smooth', block: 'center'});
      void entry.row.offsetWidth;
      entry.row.classList.add('entity-search-jump-highlight');
    }
  }, []);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setQuery(value);
      applyFilter(value, activeChip);
    },
    [applyFilter, activeChip],
  );

  const handleClear = useCallback(() => {
    setQuery('');
    setActiveChip(null);
    applyFilter('', null);
    inputRef.current?.focus();
  }, [applyFilter]);

  // Click anywhere outside the search bar → reset all filters
  useEffect(() => {
    if (query.trim().length === 0 && activeChip === null) return;

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      // Don't reset if clicking inside the search container
      if (containerRef.current?.contains(target)) return;
      // Don't reset if clicking inside an entity table or its buttons
      if ((target as Element).closest?.('.entity-copy-btn, .entity-back-link, table')) return;

      setQuery('');
      setActiveChip(null);
      applyFilter('', null);
    };

    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [query, activeChip, applyFilter]);

  const handleChipClick = useCallback(
    (chipMatch: string) => {
      const next = chipMatch === activeChip ? null : chipMatch;
      setActiveChip(next);
      applyFilter(query, next);
    },
    [applyFilter, query, activeChip],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') {
        handleClear();
        return;
      }

      const visibleMatches = matches.slice(0, MAX_RESULTS);
      if (visibleMatches.length === 0) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((prev) => {
          const next = prev < visibleMatches.length - 1 ? prev + 1 : 0;
          resultsRef.current?.children[next]?.scrollIntoView({block: 'nearest'});
          return next;
        });
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((prev) => {
          const next = prev > 0 ? prev - 1 : visibleMatches.length - 1;
          resultsRef.current?.children[next]?.scrollIntoView({block: 'nearest'});
          return next;
        });
      } else if (e.key === 'Enter' && activeIndex >= 0 && activeIndex < visibleMatches.length) {
        e.preventDefault();
        scrollToEntry(visibleMatches[activeIndex]);
      }
    },
    [handleClear, matches, activeIndex, scrollToEntry],
  );

  /** Find the best matching translated name for highlighting in dropdown */
  const getMatchingName = useCallback(
    (entry: RowEntry, needle: string): string | null => {
      if (!needle) return null;
      const lower = needle.toLowerCase();
      // Check non-English names first (user is likely searching in their language)
      for (let i = 1; i < entry.translatedNames.length; i++) {
        if (entry.translatedNames[i].toLowerCase().includes(lower)) {
          return entry.translatedNames[i];
        }
      }
      // Then English
      if (entry.englishName.toLowerCase().includes(lower)) {
        return null; // Already shown as primary
      }
      return null;
    },
    [],
  );

  const isFiltering = query.trim().length > 0 || activeChip !== null;
  const visibleMatches = matches.slice(0, MAX_RESULTS);
  const hasMore = matches.length > MAX_RESULTS;

  return (
    <div ref={containerRef} className="entity-search">
      {/* ── Category filter chips ── */}
      <div className="entity-search-chips" role="group" aria-label="Filter by platform">
        {PLATFORM_CHIPS.map((chip) => (
          <button
            key={chip.match}
            type="button"
            className={`entity-search-chip${activeChip === chip.match ? ' active' : ''}`}
            onClick={() => handleChipClick(chip.match)}
            aria-pressed={activeChip === chip.match}
          >
            {chip.label}
          </button>
        ))}
        <span className="entity-search-shortcut-hint">
          Press <kbd>/</kbd> to search
        </span>
      </div>

      {/* ── Search input ── */}
      <div className="entity-search-input-wrapper">
        <svg
          className="entity-search-icon"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          ref={inputRef}
          type="text"
          className="entity-search-input"
          placeholder="Search entities (any language)…"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          aria-label="Search entities"
          aria-expanded={isFiltering && visibleMatches.length > 0}
          aria-controls="entity-search-results"
          aria-activedescendant={
            activeIndex >= 0 ? `entity-result-${activeIndex}` : undefined
          }
          autoComplete="off"
          spellCheck={false}
          role="combobox"
        />
        {isFiltering && (
          <button
            className="entity-search-clear"
            onClick={handleClear}
            aria-label="Clear search and filters"
            type="button"
          >
            ✕
          </button>
        )}
      </div>

      {/* ── Results dropdown ── */}
      {isFiltering && (
        <div className="entity-search-results-container">
          {matchCount === 0 ? (
            <div className="entity-search-status">
              <span className="entity-search-no-results">No matching entities found</span>
            </div>
          ) : (
            <>
              {query.trim().length > 0 && (
                <ul
                  ref={resultsRef}
                  id="entity-search-results"
                  className="entity-search-results"
                  role="listbox"
                >
                  {visibleMatches.map((entry, i) => {
                    const matchedTranslation = getMatchingName(entry, query);
                    return (
                      <li
                        key={entry.key}
                        id={`entity-result-${i}`}
                        className={`entity-search-result-item${i === activeIndex ? ' active' : ''}`}
                        role="option"
                        aria-selected={i === activeIndex}
                        onClick={() => scrollToEntry(entry)}
                        onMouseEnter={() => setActiveIndex(i)}
                      >
                        <span className="entity-search-result-name">
                          {entry.englishName}
                        </span>
                        <code className="entity-search-result-key">{entry.key}</code>
                        {matchedTranslation && (
                          <span className="entity-search-result-translation">
                            {matchedTranslation}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
              <div className="entity-search-status">
                {matchCount} of {total} entities
                {hasMore && query.trim().length > 0 && (
                  <span className="entity-search-more">
                    {' '}&mdash; showing first {MAX_RESULTS}, type more to narrow down
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
