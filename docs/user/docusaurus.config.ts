import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Tibber Prices Integration',
  tagline: 'Custom Home Assistant integration for Tibber electricity prices',
  favicon: 'img/icon.svg',

  future: {
    v4: true,
  },

  url: 'https://jpawlowski.github.io',
  baseUrl: '/hass.tibber_prices/user/',

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
              return `https://github.com/jpawlowski/hass.tibber_prices/tree/${version}/docs/user/docs/${docPath}`;
            }
            return `https://github.com/jpawlowski/hass.tibber_prices/tree/main/docs/user/docs/${docPath}`;
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
        src: 'img/icon.svg',
      },
      items: [
        {
          to: '/intro',
          label: 'User Guide',
          position: 'left',
        },
        {
          href: 'https://jpawlowski.github.io/hass.tibber_prices/developer/',
          label: 'Developer Docs',
          position: 'left',
        },
        {
          type: 'docsVersionDropdown',
          position: 'right',
          dropdownActiveClassDisabled: true,
        },
        {
          type: 'html',
          position: 'right',
          value: '<a href="https://www.buymeacoffee.com/jpawlowski" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link" style="display: flex; align-items: center; gap: 0.4rem;"><img src="/hass.tibber_prices/user/img/bmc-full-logo.svg" alt="Buy Me a Coffee" class="bmc-logo-light" style="height: 28px; width: auto;" /><img src="/hass.tibber_prices/user/img/bmc-full-logo-dark.svg" alt="Buy Me a Coffee" class="bmc-logo-dark" style="height: 28px; width: auto;" /><svg width="13.5" height="13.5" aria-hidden="true" viewBox="0 0 24 24" style="margin-left: 0.15rem;"><path fill="currentColor" d="M21 13v10h-21v-19h12v2h-10v15h17v-8h2zm3-12h-10.988l4.035 4-6.977 7.07 2.828 2.828 6.977-7.07 4.125 4.172v-11z"></path></svg></a>',
        },
        {
          type: 'html',
          position: 'right',
          value: '<a href="https://github.com/jpawlowski/hass.tibber_prices" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link" aria-label="GitHub" title="GitHub Repository"><svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg></a>',
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
              to: '/intro',
            },
            {
              label: 'Developer Guide',
              href: 'https://jpawlowski.github.io/hass.tibber_prices/developer/',
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
      additionalLanguages: ['bash', 'yaml', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
