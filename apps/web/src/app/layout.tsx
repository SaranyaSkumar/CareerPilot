import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerPilot — Your next career move",
  description: "Discover opportunities, build stronger applications, and manage your career journey with AI assistance.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
