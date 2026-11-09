import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ShoeDetailView } from "@/components/catalog/ShoeDetailView";

export const metadata: Metadata = { title: "Shoe details | The Assist" };

export default async function ShoePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const shoeId = Number(id);
  if (!Number.isInteger(shoeId) || shoeId < 1) notFound();
  return <ShoeDetailView id={shoeId} />;
}
