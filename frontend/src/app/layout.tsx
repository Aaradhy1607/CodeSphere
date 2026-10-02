import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/authContext";
import { ThemeProvider } from "@/lib/themeContext";
import { ToastProvider } from "@/components/ui/Toast";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "CodeSphere | Institutional Assessment & Placement Engine",
  description: "Official institutional coding assessment, online judging sandbox, and placement readiness platform for USAR students.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var saved = localStorage.getItem('codesphere_theme');
                  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                  var theme = saved || (prefersDark ? 'dark' : 'light');
                  if (theme === 'system') {
                    theme = prefersDark ? 'dark' : 'light';
                  }
                  document.documentElement.classList.toggle('dark', theme === 'dark');
                  document.documentElement.classList.toggle('light', theme === 'light');
                  document.documentElement.setAttribute('data-theme', theme);
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="bg-[var(--bg-canvas)] text-[var(--text-primary)] min-h-screen flex flex-col antialiased selection:bg-[var(--accent-primary)] selection:text-white">
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              <Navbar />
              <main className="flex-1 w-full" id="main-content">
                {children}
              </main>
              <footer className="py-6 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] text-xs text-[var(--text-muted)]">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
                  <div>
                    <p className="font-semibold text-[var(--text-primary)]">
                      CodeSphere™ Placement & Assessment Infrastructure
                    </p>
                    <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                      University School of Automation and Robotics (USAR) • GGSIPU East Delhi Campus
                    </p>
                  </div>
                  <div className="flex items-center gap-3 font-mono text-[11px] text-[var(--text-muted)]">
                    <span className="px-2 py-0.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] font-medium text-[var(--text-secondary)]">AIML</span>
                    <span className="px-2 py-0.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] font-medium text-[var(--text-secondary)]">AIDS</span>
                    <span className="px-2 py-0.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] font-medium text-[var(--text-secondary)]">IIOT</span>
                    <span className="px-2 py-0.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] font-medium text-[var(--text-secondary)]">AR</span>
                  </div>
                </div>
              </footer>
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
