import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Tibber Prices - Developer Guide',
  tagline: 'Developer documentation for the Tibber Prices custom integration',
  favicon: 'img/logo.svg',

  future: {
    v4: true,
  },

  url: 'https://jpawlowski.github.io',
  baseUrl: '/hass.tibber_prices/developer/',

  organizationName: 'jpawlowski',
  projectName: 'hass.tibber_prices',
  deploymentBranch: 'gh-pages',
  trailingSlash: false,

  onBrokenLinks: 'warn',

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  themes: ['@docusaurus/theme-mermaid'],

  plugins: [
    'docusaurus-lunr-search',
  ],

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  headTags: [
    {
      tagName: 'link',
      attributes: {
        rel: 'preconnect',
        href: 'https://fonts.googleapis.com',
      },
    },
    {
      tagName: 'link',
      attributes: {
        rel: 'preconnect',
        href: 'https://fonts.gstatic.com',
        crossorigin: 'anonymous',
      },
    },
    {
      tagName: 'link',
      attributes: {
        rel: 'stylesheet',
        href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap',
      },
    },
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          editUrl: ({versionDocsDirPath, docPath}) => {
            if (versionDocsDirPath.includes('_versioned_')) {
              const version = versionDocsDirPath.match(/version-([^/]+)/)?.[1] || 'main';
              return `https://github.com/jpawlowski/hass.tibber_prices/tree/${version}/docs/developer/docs/${docPath}`;
            }
            return `https://github.com/jpawlowski/hass.tibber_prices/tree/main/docs/developer/docs/${docPath}`;
          },
          showLastUpdateTime: true,
          versions: {
            current: {
              label: 'Next 🚧',
              banner: 'unreleased',
              badge: true,
            },
          },
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    mermaid: {
      theme: {light: 'base', dark: 'dark'},
      options: {
        themeVariables: {
          // Light mode colors
          primaryColor: '#e6f7ff',
          primaryTextColor: '#1a1a1a',
          primaryBorderColor: '#00b9e7',
          lineColor: '#00b9e7',
          secondaryColor: '#e6fff5',
          secondaryTextColor: '#1a1a1a',
          secondaryBorderColor: '#00ffa3',
          tertiaryColor: '#fff9e6',
          tertiaryTextColor: '#1a1a1a',
          tertiaryBorderColor: '#ffb800',
          noteBkgColor: '#e6f7ff',
          noteTextColor: '#1a1a1a',
          noteBorderColor: '#00b9e7',
          // Node styling
          mainBkg: '#ffffff',
          nodeBorder: '#00b9e7',
          clusterBkg: '#f0f9ff',
          clusterBorder: '#00b9e7',
          // Font styling
          fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
          fontSize: '14px',
        },
      },
    },
    image: 'img/social-card.png',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    docs: {
      sidebar: {
        hideable: true,
        autoCollapseCategories: true,
      },
    },
    navbar: {
      title: 'Tibber Prices HA',
      logo: {
        alt: 'Tibber Prices Integration Logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          to: '/intro',
          label: 'Developer Guide',
          position: 'left',
        },
        {
          href: 'https://jpawlowski.github.io/hass.tibber_prices/user/',
          label: 'User Docs',
          position: 'left',
        },
        {
          type: 'docsVersionDropdown',
          position: 'right',
          dropdownActiveClassDisabled: true,
        },
        {
          href: 'https://github.com/jpawlowski/hass.tibber_prices',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'User Guide',
              href: 'https://jpawlowski.github.io/hass.tibber_prices/user/',
            },
            {
              label: 'Developer Guide',
              to: '/intro',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'GitHub Issues',
              href: 'https://github.com/jpawlowski/hass.tibber_prices/issues',
            },
            {
              label: 'Home Assistant Community',
              href: 'https://community.home-assistant.io/',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/jpawlowski/hass.tibber_prices',
            },
            {
              label: 'Release Notes',
              href: 'https://github.com/jpawlowski/hass.tibber_prices/releases',
            },
          ],
        },
      ],
      copyright: `Not affiliated with Tibber AS. Community-maintained custom integration. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'yaml', 'json', 'python'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
