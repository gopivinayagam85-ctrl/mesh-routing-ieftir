import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function runTests() {
  console.log('Launching Chrome from:', chromePath);
  const browser = await chromium.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });

  const page = await context.newPage();
  const consoleMessages = [];
  const pageErrors = [];
  const networkRequests = [];

  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  page.on('pageerror', err => {
    pageErrors.push(err.toString());
  });

  page.on('requestfinished', async req => {
    try {
      const resp = await req.response();
      networkRequests.push({
        url: req.url(),
        method: req.method(),
        status: resp ? resp.status() : null
      });
    } catch (_) {}
  });

  page.on('requestfailed', req => {
    networkRequests.push({
      url: req.url(),
      method: req.method(),
      error: req.failure() ? req.failure().errorText : 'failed'
    });
  });

  const results = {
    steps: [],
    consoleMessages,
    pageErrors,
    networkRequests,
    success: true
  };

  try {
    // Step 1: Load frontend
    console.log('Step 1: Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 10000 });
    const title = await page.title();
    console.log('Page Title:', title);
    results.steps.push({ step: 'Load page', title, passed: title.includes('Mesh Routing') });

    // Step 2: Check header and brand
    const brand = await page.textContent('.brand b');
    console.log('Brand text:', brand);
    results.steps.push({ step: 'Verify UI elements', brand, passed: brand === 'Mesh Routing Lab' });

    // Step 3: Verify initial topology preview state
    const topoChip = await page.textContent('.topology-panel .panel-chip');
    console.log('Initial Topology Chip:', topoChip);
    results.steps.push({ step: 'Initial topology state', topoChip, passed: topoChip === 'AWAITING RUN' });

    // Step 4: Run Incremental (IEFT-IR) simulation
    console.log('Step 4: Running Incremental simulation...');
    await page.selectOption('#algo-select-hero', 'incremental');
    await page.click('button.primary:has-text("Run simulation")');
    await page.waitForFunction(() => {
      const btn = document.querySelector('button.primary');
      return btn && btn.textContent.includes('Run simulation') && !btn.textContent.includes('Running');
    }, { timeout: 15000 });

    // Check topology nodes
    const nodeCount = await page.locator('.network-svg circle').count();
    console.log('Rendered SVG node circles count:', nodeCount);
    const pdrText = await page.locator('.metric-grid .metric').first().textContent();
    console.log('PDR Metric:', pdrText);
    results.steps.push({
      step: 'Incremental simulation execution',
      svgCircles: nodeCount,
      pdrMetric: pdrText,
      passed: nodeCount > 20 && pdrText.includes('%')
    });

    // Step 5: Run Energy-aware simulation
    console.log('Step 5: Running Energy-aware simulation...');
    await page.selectOption('#algo-select-hero', 'energy');
    await page.click('button.primary:has-text("Run simulation")');
    await page.waitForFunction(() => {
      const btn = document.querySelector('button.primary');
      return btn && btn.textContent.includes('Run simulation') && !btn.textContent.includes('Running');
    }, { timeout: 15000 });
    const algoChip = await page.textContent('.topology-panel small');
    console.log('Topology Panel Algorithm:', algoChip);
    results.steps.push({
      step: 'Energy-aware simulation execution',
      algoChip,
      passed: algoChip.includes('energy')
    });

    // Step 6: Run Shortest path simulation
    console.log('Step 6: Running Shortest path simulation...');
    await page.selectOption('#algo-select-hero', 'shortest');
    await page.click('button.primary:has-text("Run simulation")');
    await page.waitForFunction(() => {
      const btn = document.querySelector('button.primary');
      return btn && btn.textContent.includes('Run simulation') && !btn.textContent.includes('Running');
    }, { timeout: 15000 });
    const shortestChip = await page.textContent('.topology-panel small');
    console.log('Topology Panel Shortest Chip:', shortestChip);
    results.steps.push({
      step: 'Shortest path simulation execution',
      shortestChip,
      passed: shortestChip.includes('shortest')
    });

    // Step 7: Node failure and route recovery check
    console.log('Step 7: Testing node failure scenario...');
    await page.selectOption('#algo-select-hero', 'incremental');
    // Set failure count to 3
    const failureInput = page.locator('input[type="range"]').nth(5); // failure_count slider
    // Update config via React state by selecting options or filling inputs
    await page.evaluate(() => {
      // Find the Failed nodes input
      const labels = Array.from(document.querySelectorAll('.control label'));
      const failureLabel = labels.find(l => l.textContent.includes('Failed nodes'));
      if (failureLabel) {
        const input = failureLabel.parentElement.querySelector('input');
        input.value = '3';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    await page.click('button.primary:has-text("Run simulation")');
    await page.waitForFunction(() => {
      const btn = document.querySelector('button.primary');
      return btn && btn.textContent.includes('Run simulation') && !btn.textContent.includes('Running');
    }, { timeout: 15000 });
    const failureMetric = await page.locator('.metric-grid .metric').nth(2).textContent(); // Recomputations & local updates
    console.log('Recomputations & Updates with failure:', failureMetric);
    results.steps.push({
      step: 'Fault injection & route recovery',
      failureMetric,
      passed: failureMetric.includes('Local updates:')
    });

    // Step 8: Tab navigation & Comparison mode
    console.log('Step 8: Testing Algorithm Comparison tab...');
    await page.click('button.nav-item:has-text("Algorithm comparison")');
    await page.waitForTimeout(500);
    // Click Run benchmark suite
    await page.click('button.primary:has-text("Run benchmark suite")');
    await page.waitForFunction(() => {
      const btn = document.querySelector('button.primary');
      return btn && btn.textContent.includes('Run benchmark suite') && !btn.textContent.includes('Evaluating');
    }, { timeout: 25000 });
    const summaryRows = await page.locator('.table-scroll table tbody tr').count();
    console.log('Comparison table rows count:', summaryRows);
    results.steps.push({
      step: 'Comparison suite multi-algorithm execution',
      summaryRows,
      passed: summaryRows === 3
    });

    // Step 9: Method & Metrics tab
    console.log('Step 9: Testing Method & metrics tab...');
    await page.click('button.nav-item:has-text("Method & metrics"), button.nav-item:has-text("Methodology")');
    await page.waitForTimeout(500);
    const methodHeading = await page.textContent('.method-panel h2');
    console.log('Method tab heading:', methodHeading);
    results.steps.push({
      step: 'Method & metrics rendering',
      methodHeading,
      passed: methodHeading.includes('Methodology') || methodHeading.includes('What is being tested?')
    });

    // Step 10: Validation and error handling
    console.log('Step 10: Testing input validation banner...');
    await page.click('button.nav-item:has-text("Live simulation"), button.nav-item:has-text("Network Simulator"), button.nav-item:has-text("Overview")');
    await page.waitForTimeout(500);
    // Set gateway to 99 (invalid: >= nodes)
    const gwInput = page.locator('.control input[type="number"]').first();
    await gwInput.fill('99');
    await page.click('button.primary:has-text("Run simulation")');
    await page.waitForTimeout(500);
    const errorBanner = await page.textContent('.error-banner');
    console.log('Error Banner text:', errorBanner);
    results.steps.push({
      step: 'Input validation error handling',
      errorBanner,
      passed: errorBanner.includes('Gateway node ID must be less than node count')
    });
    // Dismiss error banner
    await page.click('.error-banner button');
    await page.waitForTimeout(300);
    const errorBannerAfter = await page.locator('.error-banner').count();
    results.steps.push({
      step: 'Dismiss error banner',
      errorBannerAfter,
      passed: errorBannerAfter === 0
    });

    // Step 11: Viewport responsiveness test
    console.log('Step 11: Testing responsive viewport (mobile 375x667)...');
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(500);
    const brandMobile = await page.textContent('.brand b');
    console.log('Mobile Brand text:', brandMobile);
    results.steps.push({
      step: 'Mobile viewport rendering (375x667)',
      passed: brandMobile === 'Mesh Routing Lab'
    });

  } catch (err) {
    console.error('Test execution error:', err);
    results.success = false;
    results.error = err.toString();
  } finally {
    await browser.close();
  }

  const outPath = path.resolve('..', 'research_results', 'browser_e2e_results.json');
  fs.writeFileSync(outPath, JSON.stringify(results, null, 2), 'utf-8');
  console.log('Saved browser test results to:', outPath);
}

runTests();
