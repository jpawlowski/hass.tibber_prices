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
              <h3>🏗️ Clean Architecture</h3>
              <p>
                Modular design with separation of concerns. Calculator pattern for business logic,
                coordinator-based data flow, and comprehensive caching strategies.
              </p>
            </div>
          </div>
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>🧪 Test Coverage</h3>
              <p>
                Comprehensive test suite with unit, integration, and E2E tests. Resource leak
                detection, lifecycle validation, and performance benchmarks.
              </p>
            </div>
          </div>
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>📚 Full Documentation</h3>
              <p>
                Complete API reference, architecture diagrams, coding guidelines, and
                debugging guides. Everything you need to contribute effectively.
              </p>
            </div>
          </div>
        </div>
        <div className="row margin-top--lg">
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>🔧 DevContainer Ready</h3>
              <p>
                Pre-configured development environment with all dependencies. VS Code
                integration, linting, type checking, and debugging tools included.
              </p>
            </div>
          </div>
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>⚡ Performance Focused</h3>
              <p>
                Multi-layer caching, optimized algorithms, and efficient data structures.
                Coordinator updates in &lt;500ms, sensor updates in &lt;10ms.
              </p>
            </div>
          </div>
          <div className={clsx('col col--4')}>
            <div className="text--center padding-horiz--md">
              <h3>🤝 Community Driven</h3>
              <p>
                Open source project with active development. Conventional commits,
                semantic versioning, and automated release management.
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
      title={siteConfig.title}
      description="Developer documentation for the Tibber Prices custom integration for Home Assistant">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
