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
      label: '📊 Sensors',
      items: [
        'sensors-overview',
        'sensors-average',
        'sensors-ratings-levels',
        'sensors-volatility',
        'sensors-trends',
        'sensors-timing',
        'sensors-energy-tax',
      ],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '⏰ Price Periods',
      items: ['period-calculation', 'period-relaxation'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '🎨 Dashboards & Charts',
      items: ['dynamic-icons', 'icon-colors', 'dashboard-examples', 'chart-examples'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '🤖 Automations',
      items: ['automation-examples'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '📖 Reference',
      items: ['sensor-reference', 'actions'],
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
