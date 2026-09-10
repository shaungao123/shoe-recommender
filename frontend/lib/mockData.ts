/**
 * Placeholder data for local development (NEXT_PUBLIC_USE_MOCK_API=true) and
 * the home-screen trending section until a real endpoint exists.
 * Brands/models are fictional on purpose — never present these as real shoes.
 */

import type { RecommendResponse, TrendingShoe } from "./types";

export const MOCK_LATENCY_MS = 6500;

export const mockRecommendResponse: RecommendResponse = {
  recommendations: [
    {
      id: 1,
      brand: "Voltra Athletics",
      model: "Rebound Mid '26",
      price: 139,
      image_url: null,
      specs: ["Mid cut", "Firm cushion", "11.2 oz", "Multi-surface traction"],
      explanation:
        "You said you plant hard on closeouts and change direction fast — this is built for exactly that stop-and-go. Reviewers keep flagging the herringbone as reliable on real hardwood, and the mid collar gives lockdown without slowing your first step.",
      affiliate_url: null,
    },
    {
      id: 2,
      brand: "Halcyon Sport",
      model: "Skyline Low",
      price: 118,
      image_url: null,
      specs: ["Low cut", "Soft cushion", "Runs small — size up ½"],
      explanation:
        "This is the low-maintenance pick — plush underfoot, forgiving on the ankles, and it just works for pickup runs without asking much of you. Not the flashiest shoe here, but it's the one people say they forget they're wearing.",
      affiliate_url: null,
    },
    {
      id: 3,
      brand: "Ardent",
      model: "Nightform '26",
      price: 172,
      image_url: null,
      specs: ["High cut", "Balanced cushion", "12.6 oz"],
      explanation:
        "This one leads with the colorway and the silhouette — the kind of pair that gets a second look off the court. It still holds its own on it: reviewers rate the cushioning as balanced enough for a full run, not just a photo op.",
      affiliate_url: null,
    },
  ],
};

export const trendingPlaceholder: TrendingShoe[] = [
  {
    brand: "Voltra Athletics",
    model: "Rebound Mid '26",
    price: "$139",
    blurb: "The go-to for anyone who plants hard and cuts fast.",
  },
  {
    brand: "Halcyon Sport",
    model: "Skyline Low",
    price: "$118",
    blurb: "Plush, forgiving, and easy to love off the first run.",
  },
  {
    brand: "Ardent",
    model: "Nightform '26",
    price: "$172",
    blurb: "Style-first, but reviewers say it holds up on court.",
  },
  {
    brand: "Northgate",
    model: "Basewrap 3",
    price: "$104",
    blurb: "The budget pick people keep recommending anyway.",
  },
];
