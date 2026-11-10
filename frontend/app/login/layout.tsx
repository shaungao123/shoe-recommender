import { SiteHeader } from "@/components/SiteHeader";

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SiteHeader />
      {children}
    </>
  );
}
