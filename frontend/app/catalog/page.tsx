import type { Metadata } from "next";
import { Suspense } from "react";
import { CatalogBrowser } from "@/components/catalog/CatalogBrowser";

export const metadata: Metadata = { title: "Basketball shoe catalog | The Assist", description: "Browse review-backed basketball shoes by price, position, playstyle, court use, cut, and width." };

export default function CatalogPage() { return <Suspense><CatalogBrowser /></Suspense>; }
