import React from 'react';
import DocItemFooter from '@theme-original/DocItem/Footer';
import GiscusComponent from '@site/src/components/GiscusComponent';
import { useDoc } from '@docusaurus/plugin-content-docs/client';

export default function DocItemFooterWrapper(props) {
  const { frontMatter } = useDoc();

  // Allow disabling comments per page via frontmatter
  const enableComments = frontMatter.comments !== false;

  return (
    <>
      <DocItemFooter {...props} />
      {enableComments && (
        <div style={{ marginTop: '3rem' }}>
          <p style={{
            fontSize: '0.85rem',
            color: 'var(--ifm-color-emphasis-600)',
            marginBottom: '0.75rem',
          }}>
            💬 <strong>Comments are page-specific.</strong> For a new question or idea,{' '}
            <a
              href="https://github.com/jpawlowski/hass.tibber_prices/discussions/new/choose"
              target="_blank"
              rel="noopener noreferrer"
            >
              open a dedicated Discussion on GitHub
            </a>{' '}
            so it gets its own thread and proper visibility.
          </p>
          <GiscusComponent />
        </div>
      )}
    </>
  );
}
