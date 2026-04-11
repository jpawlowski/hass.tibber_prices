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
      label: '🚀 Getting Started',
      items: ['installation', 'configuration'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '📖 Core Concepts',
      items: ['concepts', 'glossary'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '📊 Features',
      items: ['sensors', 'sensor-reference', 'period-calculation', 'dynamic-icons', 'icon-colors', 'actions'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '🎨 Visualization',
      items: ['dashboard-examples', 'chart-examples'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '🤖 Automation',
      items: ['automation-examples'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '👥 Community',
      items: ['community-examples'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '🔧 Help & Support',
      items: ['faq', 'troubleshooting'],
      collapsible: true,
      collapsed: false,
    },
  ],
};

export default sidebars;
