import { test, expect } from '@playwright/test';

test.describe('Drive Organizer E2E Workflow', () => {
  test('Complete workflow: login → scan → proposal → apply → undo', async ({ page }) => {
    // Navigate to the application
    await page.goto('http://localhost:3000');
    
    // Wait for redirect to login page
    await expect(page).toHaveURL(/.*login/);
    
    // Mock authentication - in real test, you'd use test credentials
    await page.evaluate(() => {
      // Mock successful Google OAuth
      localStorage.setItem('supabase.auth.token', 'mock-token');
      window.location.href = '/dashboard';
    });
    
    // Wait for redirect to dashboard
    await expect(page).toHaveURL(/.*dashboard/);
    
    // Verify dashboard is loaded
    await expect(page.locator('h1')).toContainText('Drive Organizer');
    
    // Start metadata ingestion
    await page.click('[data-testid="start-ingest"]');
    
    // Wait for ingestion to complete
    await expect(page.locator('[data-testid="ingest-status"]')).toContainText('done');
    
    // Verify file count is displayed
    await expect(page.locator('[data-testid="file-count"]')).toBeVisible();
    
    // Generate AI proposal
    await page.click('[data-testid="generate-proposal"]');
    
    // Wait for proposal to be generated
    await expect(page.locator('[data-testid="proposal-status"]')).toContainText('draft');
    
    // Verify tree visualization is displayed
    await expect(page.locator('[data-testid="tree-visualizer"]')).toBeVisible();
    
    // Apply the structure
    await page.click('[data-testid="apply-structure"]');
    
    // Wait for confirmation
    await expect(page.locator('[data-testid="apply-success"]')).toBeVisible();
    
    // Verify undo button is available
    await expect(page.locator('[data-testid="undo-button"]')).toBeVisible();
    
    // Perform undo operation
    await page.click('[data-testid="undo-button"]');
    
    // Wait for undo confirmation
    await expect(page.locator('[data-testid="undo-success"]')).toBeVisible();
    
    // Verify structure is reverted
    await expect(page.locator('[data-testid="proposal-status"]')).toContainText('reverted');
  });
  
  test('Error handling: invalid credentials', async ({ page }) => {
    await page.goto('http://localhost:3000/login');
    
    // Mock failed authentication
    await page.evaluate(() => {
      // Simulate auth error
      window.dispatchEvent(new CustomEvent('auth-error', { 
        detail: { message: 'Invalid credentials' } 
      }));
    });
    
    // Verify error message is displayed
    await expect(page.locator('[data-testid="auth-error"]')).toContainText('Invalid credentials');
  });
  
  test('Settings page functionality', async ({ page }) => {
    // Navigate to settings (assuming authenticated)
    await page.goto('http://localhost:3000/settings');
    
    // Update preferences
    await page.fill('[data-testid="max-file-size"]', '50');
    await page.check('[data-testid="ignore-large"]');
    await page.click('[data-testid="save-preferences"]');
    
    // Verify success message
    await expect(page.locator('[data-testid="preferences-saved"]')).toBeVisible();
  });
}); 