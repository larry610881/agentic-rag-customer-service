const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });

  // Visit homepage first
  const homePage = await context.newPage();
  console.log('Visiting homepage...');
  await homePage.goto('https://online.carrefour.com.tw/', { waitUntil: 'networkidle', timeout: 30000 });
  console.log(`Title: ${await homePage.title()}`);

  // Try using the search box on homepage
  try {
    // Look for search input
    const searchInput = await homePage.$('input[type="search"], input[name="q"], input[placeholder*="搜尋"], [class*="search"] input');
    if (searchInput) {
      console.log('Found search input, typing...');
      await searchInput.fill('統一麵');
      await homePage.waitForTimeout(2000);

      // Check for autocomplete/suggestions
      const suggestions = await homePage.evaluate(() => {
        const items = [];
        document.querySelectorAll('[class*="suggest"] a, [class*="autocomplete"] a, [class*="search-result"] a').forEach(a => {
          items.push({ href: a.href, text: (a.textContent || '').trim().substring(0, 60) });
        });
        return items;
      });
      console.log(`Suggestions: ${JSON.stringify(suggestions)}`);

      // Submit search
      await searchInput.press('Enter');
      await homePage.waitForTimeout(5000);
      console.log(`After search URL: ${homePage.url()}`);
      console.log(`After search title: ${await homePage.title()}`);

      // Check for product links
      const productLinks = await homePage.evaluate(() => {
        const links = [];
        document.querySelectorAll('a[href]').forEach(a => {
          const href = a.getAttribute('href') || '';
          if (href.includes('/product') || href.includes('/item') || href.match(/\/\d{5,}/)) {
            links.push({ href: a.href, text: (a.textContent || '').trim().substring(0, 80) });
          }
        });
        // deduplicate by href
        const seen = new Set();
        return links.filter(l => { if (seen.has(l.href)) return false; seen.add(l.href); return true; }).slice(0, 10);
      });

      if (productLinks.length > 0) {
        console.log(`\nFound ${productLinks.length} product links:`);
        productLinks.forEach(l => console.log(`  ${l.href}\n    ${l.text}`));
      } else {
        console.log('No product links found after search');
        const bodyText = await homePage.evaluate(() => (document.body?.innerText || '').substring(0, 500));
        console.log(`Body: ${bodyText}`);
      }
    } else {
      console.log('No search input found');
      // Dump all inputs
      const inputs = await homePage.evaluate(() => {
        return Array.from(document.querySelectorAll('input')).map(i => ({
          type: i.type, name: i.name, placeholder: i.placeholder, className: i.className.substring(0, 50),
        }));
      });
      console.log('Inputs:', JSON.stringify(inputs, null, 2));
    }
  } catch (e) {
    console.log(`Search error: ${e.message.substring(0, 300)}`);
  }

  await browser.close();
})();
