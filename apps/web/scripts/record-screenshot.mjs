import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    recordVideo: { dir: '/app/verification/video' }
  });
  const page = await context.newPage();

  console.log("Navigating to local dev server...");
  await page.goto('http://localhost:5173/map');

  // Wait for map to initialize and load
  await page.waitForTimeout(3000);

  // Focus a specific area or just wait for map rendering
  console.log("Taking screenshot...");
  await page.screenshot({ path: '/app/verification/verification.png' });

  // Wait a bit to ensure video captures the stable state
  await page.waitForTimeout(2000);

  await context.close(); // Saves the video
  await browser.close();
  console.log("Done.");
})();
