import type { Metadata } from "next";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import { AppNav } from "@/components/workflow/AppNav";

export const metadata: Metadata = {
  title: "CTFJudge Workflow",
  description: "Visual workflow for comparing student submissions with a golden solution",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <body><AppNav />{children}</body>
    </html>
  );
}

