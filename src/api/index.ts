import express from 'express';

import AnalyzeProductRequestSchema from '../schema/scrape-product.js';
import { analyzeAndExtractProductData } from '../services/product-service.js';

const router = express.Router();

router.post('/analyze-and-extract-product-data', async (req, res) => {
  try {
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
  } catch (error) {
    // For now, simple error output
    res.status(500).json({
      message: 'Failed to analyze product',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
});

export default router;
