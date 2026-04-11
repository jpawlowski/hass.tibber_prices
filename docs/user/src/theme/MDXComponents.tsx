/**
 * Extend the default MDXComponents so that <EntityRef> and <EntitySearch>
 * are available in every .mdx / .md page without explicit imports.
 */
import MDXComponents from '@theme-original/MDXComponents';
import EntityRef from '@site/src/components/EntityRef';
import EntitySearch from '@site/src/components/EntitySearch';

export default {
  ...MDXComponents,
  EntityRef,
  EntitySearch,
};
