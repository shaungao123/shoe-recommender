import { SiteHeader } from "@/components/SiteHeader";

export default function ProfileLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SiteHeader />
      {children}
    </>
  );
}
