// pdf_render.js <root> <date...> — print html/DATE.html to pdf/DATE_Market_Intelligence.pdf with the
// archive footer, and check desktop/mobile layout (no horizontal overflow, nine section headings).
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
(async () => {
  const [root, ...dates] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const out = {};
  for (const date of dates) {
    const html = fs.readFileSync(path.join(root, 'html', date + '.html'), 'utf8');
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.setContent(html, { waitUntil: 'load' });
    const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
      headings: document.querySelectorAll('h2[id]').length, citations: document.querySelectorAll('.source-cite').length }));
    if (layout.scroll > layout.width || layout.headings !== 9) throw new Error(date + ' desktop layout failure ' + JSON.stringify(layout));
    if (date === dates[0]) {
      await page.screenshot({ path: path.join(root, 'checks', 'desktop-preview.png') });
      await page.locator('#retail').scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(root, 'checks', 'retail-preview.png') });
    }
    await page.evaluate(() => document.querySelectorAll('details').forEach(x => x.open = true));
    const pdf = path.join(root, 'pdf', date + '_Market_Intelligence.pdf');
    await page.pdf({ path: pdf, format: 'A4', printBackground: true, margin: { top: '14mm', bottom: '16mm', left: '14mm', right: '14mm' },
      displayHeaderFooter: true, headerTemplate: '<span></span>',
      footerTemplate: '<div style="font-family:Arial;font-size:8px;width:100%;text-align:center;color:#8993a2">' + date + ' · Market Intelligence Briefing · <span class="pageNumber"></span> / <span class="totalPages"></span></div>' });
    await page.setViewportSize({ width: 390, height: 844 }); await page.setContent(html, { waitUntil: 'load' });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    if (overflow) throw new Error(date + ' mobile overflow');
    if (date === dates[0]) await page.screenshot({ path: path.join(root, 'checks', 'mobile-preview.png') });
    out[date] = { layout, mobile_overflow: false };
    console.log(date, 'pdf ok', layout.citations, 'citation links');
  }
  fs.writeFileSync(path.join(root, 'checks', 'pdf_layout.json'), JSON.stringify(out, null, 1));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
