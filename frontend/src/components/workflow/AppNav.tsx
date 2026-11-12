"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function AppNav() {
  const pathname = usePathname();
  return (
    <nav className="app-nav" aria-label="Khu vực chính">
      <Link href="/" aria-current={pathname === "/" ? "page" : undefined}>Cấu hình workflow</Link>
      <Link href="/prod" aria-current={pathname.startsWith("/prod") ? "page" : undefined}>Chấm bài</Link>
      <Link href="/models" aria-current={pathname.startsWith("/models") ? "page" : undefined}>AI Models</Link>
    </nav>
  );
}
