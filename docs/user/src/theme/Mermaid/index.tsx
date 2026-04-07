import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import OriginalMermaid from '@theme-original/Mermaid';
import type MermaidType from '@theme/Mermaid';
import type { WrapperProps } from '@docusaurus/types';

type Props = WrapperProps<typeof MermaidType>;

export default function MermaidWrapper(props: Props): React.JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
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

  // Keyboard + body-scroll lock while overlay is open
  useEffect(() => {
    if (!overlayOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [overlayOpen, handleClose]);

  return (
    <div ref={containerRef} className="mermaid-zoom-wrapper">
      <OriginalMermaid {...props} />
      <button
        className="mermaid-zoom-btn"
        onClick={handleOpen}
        aria-label="View diagram enlarged"
        title="View enlarged"
      >
        {/* Expand / fullscreen icon */}
        <svg
          viewBox="0 0 24 24"
          width="15"
          height="15"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="15 3 21 3 21 9" />
          <polyline points="9 21 3 21 3 15" />
          <line x1="21" y1="3" x2="14" y2="10" />
          <line x1="3" y1="21" x2="10" y2="14" />
        </svg>
      </button>

      {mounted &&
        overlayOpen &&
        createPortal(
          <div
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
