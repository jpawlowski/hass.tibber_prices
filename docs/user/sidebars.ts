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
      link: { type: 'doc', id: 'installation' },
      items: [
        'installation',
        {
          type: 'category',
          label: '⚙️ Configuration',
          link: { type: 'doc', id: 'configuration' },
          items: [
            'config-general',
            'config-currency',
            'config-price-rating',
            'config-price-level',
            'config-volatility',
            'config-best-price',
            'config-peak-price',
            'config-price-trend',
            'config-chart-export',
            'config-runtime-overrides',
          ],
          collapsible: true,
          collapsed: true,
        },
      ],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '📖 Core Concepts',
      link: { type: 'doc', id: 'concepts' },
      items: ['concepts', 'glossary'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '📊 Sensors',
      link: { type: 'doc', id: 'sensors-overview' },
      items: [
        'sensors-overview',
        'sensors-average',
        'sensors-ratings-levels',
        'sensors-volatility',
        'sensors-trends',
        'sensors-price-phases',
        'sensors-timing',
        'sensors-energy-tax',
      ],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '⏰ Price Periods',
      link: { type: 'doc', id: 'period-calculation' },
      items: ['period-calculation', 'period-relaxation'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '🎨 Dashboards & Charts',
      link: { type: 'doc', id: 'dashboard-examples' },
      items: ['dynamic-icons', 'icon-colors', 'dashboard-examples', 'chart-examples'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '🤖 Automations & Usage',
      link: { type: 'doc', id: 'automation-examples' },
      items: ['automation-examples'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '⚡ Actions',
      link: { type: 'doc', id: 'actions' },
      items: ['actions', 'scheduling-actions', 'plan-charging-action', 'chart-actions', 'data-actions'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '📖 Reference',
      link: { type: 'doc', id: 'sensor-reference' },
      items: ['sensor-reference'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '👥 Community',
      link: { type: 'doc', id: 'community-examples' },
      items: ['community-examples'],
      collapsible: true,
      collapsed: false,
    },
    {
      type: 'category',
      label: '🔧 Help & Support',
      link: { type: 'doc', id: 'faq' },
      items: ['faq', 'troubleshooting'],
      collapsible: true,
      collapsed: false,
    },
  ],
};

export default sidebars;
