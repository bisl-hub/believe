const puppeteer = require('puppeteer');
const fs = require('fs');

(async () => {
  const browser = await puppeteer.launch({ 
    headless: "new",
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--ignore-certificate-errors', '--window-size=1920,1080']
  });
  const page = await browser.newPage();
  
  // Navigate to login and authenticate
  await page.goto('https://believe.kaist.ac.kr/login', {waitUntil: 'networkidle0'});
  await page.type('input[type="email"]', 'uiyunkim@kaist.ac.kr');
  await page.type('input[type="password"]', '1234');
  await Promise.all([
    page.click('button[type="submit"]'),
    page.waitForNavigation({ waitUntil: 'networkidle0' }),
  ]);

  // Navigate to an existing Job that is completed
  console.log("Navigating to Job 278...");
  await page.goto('https://believe.kaist.ac.kr/jobs/278', {waitUntil: 'domcontentloaded'});
  
  // Immediately take a screenshot right after DOM load (this is the 2-second window)
  console.log("Taking initial loading screenshot...");
  await page.screenshot({path: 'debug_initial.png', fullPage: true});
  
  // Wait 3 seconds for data to load
  await new Promise(r => setTimeout(r, 3000));
  
  console.log("Taking loaded screenshot...");
  await page.screenshot({path: 'debug_loaded.png', fullPage: true});

  await browser.close();
  console.log("Done");
})();
