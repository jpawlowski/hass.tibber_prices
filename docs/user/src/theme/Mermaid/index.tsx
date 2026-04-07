import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import OriginalMermaid from '@theme-original/Mermaid';
import type MermaidType from '@theme/Mermaid';
import type { WrapperProps } from '@docusaurus/types';

type Props = WrapperProps<typeof MermaidType>;

export default function MermaidWrapper(props: Props): React.JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const lightboxRef = useRef<HTMLDivElement>(null);
  const [overlayOpen, setOverlayOpen] = useState(false);
  const [svgMarkup, setSvgMarkup] = useState('');
  const [mounted, setMounted] = useState(false);

  // Only run portals client-side (SSR safety)
  useEffect(() => {
    setMounted(true);
  }, []);

  const handleOpen = useCallback(() => {
    const svg = containerRef.current?.querySelector('svg');
    if (!svg) return;
    // Clone the SVG and strip fixed dimensions so it scales freely
    const clone = svg.cloneNode(true) as SVGElement;
    clone.removeAttribute('width');
    clone.removeAttribute('height');
    clone.style.cssText = 'width:100%;height:auto;display:block;';
    setSvgMarkup(clone.outerHTML);
    setOverlayOpen(true);
  }, []);

  const handleClose = useCallback(() => {
    setOverlayOpen(false);
  }, []);

  // Keyboard + body-scroll lock + focus trap while overlay is open
  useEffect(() => {
    if (!overlayOpen) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleClose();
        return;
      }
      // Focus trap: keep Tab/Shift+Tab inside the lightbox
      if (e.key === 'Tab' && lightboxRef.current) {
        const focusable = lightboxRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';

    // Move focus into the lightbox on open
    const closeBtn = lightboxRef.current?.querySelector<HTMLElement>('button');
    closeBtn?.focus();

    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [overlayOpen, handleClose]);

  return (
    <div
      ref={containerRef}
      className="mermaid-zoom-wrapper"
      onClick={handleOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleOpen();
        }
      }}
      aria-label="View diagram enlarged"
    >
      <OriginalMermaid {...props} />
      {/* Hover hint — pointer-events:none so it never swallows clicks */}
      <div className="mermaid-zoom-hint" aria-hidden="true">
        <div className="mermaid-zoom-hint-badge">
          <svg
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="11" y1="8" x2="11" y2="14" />
            <line x1="8" y1="11" x2="14" y2="11" />
          </svg>
          Enlarge
        </div>
      </div>

      {mounted &&
        overlayOpen &&
        createPortal(
          <div
            ref={lightboxRef}
            className="mermaid-lightbox"
            role="dialog"
            aria-modal="true"
            aria-label="Enlarged diagram"
            onClick={handleClose}
          >
            <div
              className="mermaid-lightbox-inner"
              onClick={(e) => e.stopPropagation()}
              // Safe: SVG content is cloned from our own rendered DOM node
              dangerouslySetInnerHTML={{ __html: svgMarkup }}
            />
            <button
              className="mermaid-lightbox-close"
              onClick={handleClose}
              aria-label="Close enlarged view"
              title="Close (Esc)"
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>,
          document.body,
        )}
    </div>
  );
}
