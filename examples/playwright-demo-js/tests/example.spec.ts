import { test, expect } from '@playwright/test';

// Deliberately brittle: the button's visible text is "Sign In", but this test
// still looks for the old copy "Log In". AutoHeal should diagnose the stale
// selector and fix it to match the current page content.
test('user can sign in', async ({ page }) => {
  await page.setContent(`
    <html>
      <body>
        <button id="submit-btn">Sign In</button>
      </body>
    </html>
  `);

  await page.click('text=Log In');
  await expect(page.locator('#submit-btn')).toBeVisible();
});
