const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ 
    headless: "new",
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  
  page.on('console', async (msg) => {
    const args = await Promise.all(msg.args().map(a => a.jsonValue()));
    console.log('LOG:', ...args);
  });

  await page.goto('https://believe.kaist.ac.kr/login', {waitUntil: 'networkidle0'});
  await page.type('input[type="email"]', 'uiyunkim@kaist.ac.kr');
  await page.type('input[type="password"]', '1234');
  await Promise.all([
    page.click('button[type="submit"]'),
    page.waitForNavigation({ waitUntil: 'networkidle0' }),
  ]);

  console.log("Navigating to Job 277...");
  await page.goto('https://believe.kaist.ac.kr/jobs/277', {waitUntil: 'domcontentloaded'});
  await new Promise(r => setTimeout(r, 4000));
  await browser.close();
})();
