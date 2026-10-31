import type { Config } from "@netlify/functions";
import { handleApi } from "../lib/apiHandler.ts";

export default async (req: Request): Promise<Response> => handleApi(req);

// Exactly one rate-limit rule: the free plan allows two per project, and the
// other is left free. Over-limit requests get a 429 from the platform before
// this code runs.
export const config: Config = {
  path: ["/api/jobs", "/api/jobs/:id", "/api/meta"],
  rateLimit: {
    windowLimit: 60,
    windowSize: 60,
    aggregateBy: ["ip", "domain"],
  },
};
