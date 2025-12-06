import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';
import {useColorMode} from '@docusaurus/theme-common';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  const {colorMode} = useColorMode();
  const headerUrl = useBaseUrl(colorMode === 'dark' ? '/img/header-dark.svg' : '/img/header.svg');
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <div style={{ marginBottom: '2rem' }}>
          <img src={headerUrl} alt="Tibber Prices for Tibber" style={{ maxWidth: '600px', width: '100%', height: 'auto' }} />
        </div>
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <div className={styles.buttons}>
          <Link
            className="button button--secondary button--lg"
            to="/intro">
            Get Started →
          </Link>
        </div>
      </div>
    </header>
  );
}

function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>⚡ Quarter-Hourly Precision</h3>
              <p>
                Track electricity prices with 15-minute intervals. Get accurate price data
                synchronized with your Tibber smart meter for optimal energy planning.
              </p>
            </div>
          </div>
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>📊 Smart Price Analysis</h3>
              <p>
                Automatic detection of best and peak price periods with configurable filters.
                Statistical analysis with trailing/leading 24h averages for context.
              </p>
            </div>
          </div>
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>🎨 Beautiful Visualizations</h3>
              <p>
                Auto-generated ApexCharts configurations with dynamic Y-axis scaling.
                Dynamic icons and color-coded sensors for stunning dashboards.
              </p>
            </div>
          </div>
        </div>
        <div className="row margin-top--lg">
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>🤖 Automation Ready</h3>
              <p>
                Control energy-intensive appliances based on price levels. Run dishwashers,
                heat pumps, and EV chargers during cheap periods automatically.
              </p>
            </div>
          </div>
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>💰 Multi-Currency Support</h3>
              <p>
                Full support for EUR (ct), NOK (øre), SEK (öre) with proper minor units.
                Display prices the way you're used to seeing them.
              </p>
            </div>
          </div>
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>🔧 HACS Integration</h3>
              <p>
                Easy installation via Home Assistant Community Store. Regular updates and
                active development with comprehensive documentation.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title="Home"
      description="Custom Home Assistant integration for Tibber electricity price management">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
