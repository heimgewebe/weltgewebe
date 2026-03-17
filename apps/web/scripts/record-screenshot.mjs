// record-screenshot.mjs
import puppeteer from "puppeteer";

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto("http://localhost:5173/map");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "public/demo.png", fullPage: true });
  console.log("✅ Screenshot gespeichert: public/demo.png");
  await browser.close();
})();
