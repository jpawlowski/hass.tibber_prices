import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.
 */
const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    'intro',
    {
      type: 'category',
      label: '🏗️ Architecture',
      link: { type: 'doc', id: 'architecture' },
      items: ['architecture', 'timer-architecture', 'caching-strategy', 'api-reference'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '💻 Development',
      link: { type: 'doc', id: 'setup' },
      items: ['setup', 'coding-guidelines', 'critical-patterns', 'repairs-system', 'debugging'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '📐 Advanced Topics',
      link: { type: 'doc', id: 'period-calculation-theory' },
      items: ['period-calculation-theory', 'refactoring-guide', 'performance', 'recorder-optimization'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '📝 Contributing',
      link: { type: 'doc', id: 'contributing' },
      items: ['contributing'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '🚀 Release',
      link: { type: 'doc', id: 'release-management' },
      items: ['release-management', 'testing'],
      collapsible: true,
      collapsed: false,
    },
  ],
};

export default sidebars;
