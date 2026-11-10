import { SiteHeader } from "@/components/SiteHeader";

export default function CatalogLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SiteHeader />
      {children}
    </>
  );
}
