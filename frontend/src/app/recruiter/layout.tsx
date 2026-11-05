import { AppShell } from "@/components/app/shell";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <AppShell role="recruiter">{children}</AppShell>;
}
