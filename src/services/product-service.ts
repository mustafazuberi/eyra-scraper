import type { Browser, Page } from 'puppeteer';

import axios from 'axios';
import { executablePath } from 'puppeteer';
import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';

import { env } from '../env.js';

puppeteer.use(StealthPlugin());

export type AnalyzeProductRequestDto = {
  url: string;
  countryCode?: string;
  userAgent?: string;
};

export type ProductAnalysisResult = {
  validation: {
    isDetailPage: boolean;
    reason: string;
  };
  productData: null | {
    title: string;
    price_value: string;
    currency: string;
    imageUrl: string;
  };
};

type ProxyConfig = {
  username: string;
  password: string;
  host: string;
  port: number;
};

function generateProxyConfig(countryCode: string = 'US'): ProxyConfig {
  const username = 'mustafazub4';
  const password = `bFdWY6V7WXjAIi1qXi6N_country-${countryCode.toUpperCase()}`;
  const host = 'core-residential.evomi.com';
  const port = 1000;
  return { username, password, host, port };
}

async function launchBrowser({ opts, proxyObj }: { opts: AnalyzeProductRequestDto; proxyObj: ProxyConfig }) {
  console.log("Launching browser with options: ");  
  const userAgent = opts.userAgent
    || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36';

  const launchArgs = [
    '--disable-dev-shm-usage',
    '--disable-accelerated-2d-canvas',
    '--no-first-run',
    '--no-zygote',
    '--disable-gpu',
    '--no-sandbox',
    '--disable-blink-features=AutomationControlled',
    '--disable-setuid-sandbox',
    '--disable-features=IsolateOrigins,site-per-process',
    `--user-agent=${userAgent}`,
    `--proxy-server=${proxyObj.host}:${proxyObj.port}`,
  ];

  return puppeteer.launch({
    headless: true,
    args: launchArgs,
    executablePath: executablePath(),
  });
}

const FIELDS_QUERY = `{
  page_validation {
    is_detail_page(Determine if this page focuses on a single specific product or item, not a category or list of multiple items.)
    reason(Explain briefly why this page is or isn’t identified as a single product detail page — mention clues like multiple prices, multiple product titles, or one clearly focused layout.)
  }
  product {
    title(The main visible name or heading of the single primary product on the page.)
    price(The active numeric selling price shown for that product, excluding old or discounted prices.)
    currency(The currency symbol or code displayed with the main price, such as $, USD, €, or GBP.)
    image_url(The URL of the main product image displayed on the page.)
  }
}`;

function getAgentQLApiKey(): string {
  return env.AGENTQL_API_KEY || '';
}

async function setupPage(params: AnalyzeProductRequestDto) {
  console.log("Setting up page for URL: ", params.url);
  const { url, countryCode } = params;
  const proxyObj = generateProxyConfig(countryCode || 'US');
  console.log("Proxy object: ", proxyObj);
  let browser: Browser | undefined;
  let page: Page | undefined;
  try {
    browser = await launchBrowser({ opts: params, proxyObj });
    page = await browser.newPage();
    await page.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    );
    await page.authenticate({
      username: proxyObj.username,
      password: proxyObj.password,
    });
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      const type = req.resourceType();
      if (['image', 'media', 'font'].includes(type))
        req.abort();
      else req.continue();
    });
    try {
      await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });
      await page.setViewport({ width: 1600, height: 1200 });
    }
    catch (error) {
      console.error('[product:setupPage] networkidle timed out, retrying with domcontentloaded', error);
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    }
    const pageHtml = await page.content();
    if (!pageHtml) {
      await browser.close();
      return null;
    }
    await browser.close();
    return pageHtml;
  }
  catch (error) {
    if (browser)
      await browser.close();
    console.error('[product:setupPage] Error:', error);
    return null;
  }
}

async function extractProduct(pageHtml: string) {
  try {
    console.log("Extracting product from page HTML");
    const response = await axios.post(
      'https://api.agentql.com/v1/query-data',
      {
        query: FIELDS_QUERY,
        html: pageHtml,
        params: { mode: 'fast' },
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': getAgentQLApiKey(),
        },
      },
    );
    const scrapedData = response.data.data;
    console.log("Scraped data: ", scrapedData);
    return {
      validation: {
        isDetailPage: scrapedData.page_validation.is_detail_page,
        reason: scrapedData.page_validation.reason,
      },
      productData: {
        title: scrapedData.product.title,
        price_value: scrapedData.product.price,
        currency: scrapedData.product.currency,
        imageUrl: scrapedData.product.image_url,
      },
    };
  }
  catch (error) {
    console.error('[product:extractProduct] Error:', error);
    return {
      validation: {
        isDetailPage: false,
        reason: 'Oops! We couldn’t get the product info. Try again.',
      },
      productData: null,
    };
  }
}

export async function analyzeAndExtractProductData(
  params: AnalyzeProductRequestDto,
): Promise<ProductAnalysisResult> {
  try {
    console.log("Started analyzing and extracting product data");
    const page = await setupPage(params);
    if (!page) {
      return {
        validation: {
          isDetailPage: false,
          reason: 'Oops! We couldn’t get the product info. Try again.',
        },
        productData: null,
      };
    }
    console.log("Page setup complete, extracting product");
    return await extractProduct(page);
  }
  catch (error) {
    console.error('[product:analyzeAndExtractProductData] Error:', error);
    return {
      validation: {
        isDetailPage: false,
        reason: 'Unexpected error occurred. Try again later.',
      },
      productData: null,
    };
  }
}
