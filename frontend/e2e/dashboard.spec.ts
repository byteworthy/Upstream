import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Set up mock authentication token
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-token-for-testing');
      localStorage.setItem(
        'user',
        JSON.stringify({
          id: 1,
          email: 'admin@example.com',
          first_name: 'Admin',
          last_name: 'User',
        })
      );
    });
  });

  test('should display dashboard with metrics', async ({ page }) => {
    await page.goto('/dashboard');

    // Check for dashboard heading
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();

    // Check for metric cards
    await expect(page.getByText(/total claims|claims processed/i)).toBeVisible();
  });

  test('should display navigation sidebar', async ({ page }) => {
    await page.goto('/dashboard');

    // Check sidebar navigation items
    await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /claim scores/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /work queue/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /alerts/i })).toBeVisible();
  });

  test('should navigate to claim scores page', async ({ page }) => {
    await page.goto('/dashboard');

    // Click on Claim Scores link
    await page.getByRole('link', { name: /claim scores/i }).click();

    // Should navigate to claim scores page
    await expect(page).toHaveURL(/claim-scores/);
  });

  test('should navigate to work queue page', async ({ page }) => {
    await page.goto('/dashboard');

    // Click on Work Queue link
    await page.getByRole('link', { name: /work queue/i }).click();

    // Should navigate to work queue page
    await expect(page).toHaveURL(/work-queue/);
  });

  test('should display theme toggle button', async ({ page }) => {
    await page.goto('/dashboard');

    // Check for theme toggle
    const themeToggle = page.getByRole('button', { name: /switch to (light|dark) mode/i });
    await expect(themeToggle).toBeVisible();
  });

  test('should toggle dark mode', async ({ page }) => {
    await page.goto('/dashboard');

    // Click theme toggle
    const themeToggle = page.getByRole('button', { name: /switch to (light|dark) mode/i });
    await themeToggle.click();

    // Check that theme class changes on html element
    const html = page.locator('html');
    await expect(html).toHaveClass(/dark|light/);
  });
});
