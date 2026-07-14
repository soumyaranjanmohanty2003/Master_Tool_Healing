import { test, expect } from '@playwright/test';
test('user can sign in', async ({ page }) => {
  await page.setContent(`
    <html>
      <body>
        <button id="submit-btn">Sign In</button>
      </body>
    </html>
  `);

  await page.click('text=Sign In');
  await expect(page.locator('#submit-btn')).toBeVisible();
});
