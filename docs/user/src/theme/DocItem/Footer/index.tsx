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
          <GiscusComponent />
        </div>
      )}
    </>
  );
}
