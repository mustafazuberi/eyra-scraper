import { z } from 'zod';

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

export type AnalyzeProductRequestDto = z.infer<
  typeof AnalyzeProductRequestSchema
>;
