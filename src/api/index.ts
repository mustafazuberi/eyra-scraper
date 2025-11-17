import express from 'express';
import { z } from 'zod';

import { analyzeAndExtractProductData } from '../services/product-service.js';

export const AnalyzeProductRequestSchema = z.object({
    url: z.string().url('Invalid URL format'),
    cookies: z.any().optional(),
    countryCode: z.string(),
    userAgent: z.string(),
    locale: z.string(),
    timezoneId: z.string(),
    geolocation: z.any().optional(),
    acceptLanguage: z.string(),
  });

const router = express.Router();

router.post('/analyze-and-extract-product-data', async (req, res) => {
  try {
    console.log('req.body', req.body);
    const parseResult = AnalyzeProductRequestSchema.safeParse(req.body);

    if (!parseResult.success) {
      return res.status(400).json({
        message: 'Invalid request payload',
        issues: parseResult.error.issues,
      });
    }

    const args = parseResult.data;
    const result = await analyzeAndExtractProductData(args);

    res.json({
      data: result,
      message: 'Product analysis completed successfully',
    });
  }
  catch (error) {
    // For now, simple error output
    res.status(500).json({
      message: 'Failed to analyze product',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
});

export default router;
