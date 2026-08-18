import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/features/auth";
import { SiteShell } from "@/shared/layout";
import { ThemeProvider, ThemeScript } from "@/shared/theme";
import { ToastProvider } from "@/shared/ui";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Analyse-moi ça",
  description: "Collez du texte, obtenez une analyse — résultat mis en cache et partageable.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="fr"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <ThemeScript />
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <SiteShell>{children}</SiteShell>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
