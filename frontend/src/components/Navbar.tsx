"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { useTheme } from "@/lib/themeContext";
import { DemoSwitcherModal } from "./DemoSwitcherModal";
import {
  Code2, LayoutDashboard, Calendar, Trophy, Sparkles,
  Users, BarChart3, Database, LogOut, ArrowRightLeft, Menu, X,
  Sun, Moon, Shield
} from "lucide-react";

export function Navbar() {
  const { user, logout, isAdmin } = useAuth();
  const { resolvedTheme, toggleTheme } = useTheme();
  const pathname = usePathname();
  const router = useRouter();
  const [isDemoModalOpen, setIsDemoModalOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  if (!user) return null;

  const studentLinks = [
    { name: "Dashboard", href: "/student/dashboard", icon: LayoutDashboard },
    { name: "Exams", href: "/student/assessments", icon: Shield },
    { name: "Contests", href: "/student/events", icon: Calendar },
    { name: "Leaderboard", href: "/student/leaderboard", icon: Trophy },
    { name: "AI Reports", href: "/student/reports", icon: Sparkles },
  ];

  const adminLinks = [
    { name: "Command Center", href: "/admin/dashboard", icon: LayoutDashboard },
    { name: "Assessments", href: "/admin/assessments", icon: Shield },
    { name: "Contests", href: "/admin/events", icon: Calendar },
    { name: "Question Bank", href: "/admin/questions", icon: Database },
    { name: "AI Lab", href: "/admin/ai-generator", icon: Sparkles },
    { name: "Roster", href: "/admin/students", icon: Users },
    { name: "Analytics", href: "/admin/analytics", icon: BarChart3 },
    { name: "Leaderboards", href: "/admin/leaderboards", icon: Trophy },
  ];

  const navLinks = isAdmin ? adminLinks : studentLinks;

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  const branch = user.student_profile?.branch || (isAdmin ? "PLACEMENT CELL" : "USAR");
  const year = user.student_profile?.academic_year ? `Year ${user.student_profile.academic_year}` : "";

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-[var(--bg-surface)]/95 backdrop-blur-md border-b border-[var(--border-subtle)] transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 sm:h-16">
            
            {/* Brand / Logo */}
            <div className="flex items-center gap-6 lg:gap-8">
              <Link
                href={isAdmin ? "/admin/dashboard" : "/student/dashboard"}
                className="flex items-center gap-2.5 group focus-visible:outline-none rounded-md p-1"
                aria-label="CodeSphere Home"
              >
                <div className="w-8 h-8 rounded-md bg-[var(--accent-primary)] flex items-center justify-center text-white font-bold shadow-sm">
                  <Code2 className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-sm tracking-tight text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] transition">
                      CodeSphere
                    </span>
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-[var(--accent-subtle)] text-[var(--accent-text)] border border-[var(--accent-border)]">
                      USAR
                    </span>
                  </div>
                  <p className="text-[10px] text-[var(--text-muted)] font-medium tracking-tight hidden sm:block">
                    Assessment & Placement
                  </p>
                </div>
              </Link>

              {/* Desktop Nav Links */}
              <nav className="hidden lg:flex items-center gap-1" aria-label="Main Navigation">
                {navLinks.map((link) => {
                  const Icon = link.icon;
                  const isActive = pathname === link.href || (pathname.startsWith(`${link.href}/`) && link.href !== "/admin/events" && link.href !== "/student/events");
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors focus-visible:outline-none ${
                        isActive
                          ? "bg-[var(--accent-primary)] text-white shadow-sm"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]"
                      }`}
                      aria-current={isActive ? "page" : undefined}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      {link.name}
                    </Link>
                  );
                })}
              </nav>
            </div>

            {/* Right Side Controls */}
            <div className="hidden sm:flex items-center gap-2.5">
              {/* Theme Toggle Button */}
              <button
                type="button"
                onClick={toggleTheme}
                className="p-2 rounded-md bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)] transition focus-visible:outline-none"
                title={`Switch to ${resolvedTheme === "dark" ? "Light" : "Dark"} mode`}
                aria-label="Toggle Theme"
              >
                {resolvedTheme === "dark" ? (
                  <Sun className="w-4 h-4 text-[var(--status-warning-text)]" />
                ) : (
                  <Moon className="w-4 h-4 text-[var(--text-primary)]" />
                )}
              </button>

              {/* Role Switcher Quick Pill */}
              <button
                type="button"
                onClick={() => setIsDemoModalOpen(true)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:border-[var(--border-default)] transition shadow-xs focus-visible:outline-none"
                title="Switch demo profile / role"
              >
                <ArrowRightLeft className="w-3.5 h-3.5 text-[var(--accent-primary)] shrink-0" />
                <span className="text-[11px] text-[var(--text-muted)]">Role:</span>
                <span className="font-semibold text-[var(--text-primary)] truncate max-w-[130px]">
                  {isAdmin ? "Admin" : `${user.student_profile?.branch || "Student"} (Yr ${user.student_profile?.academic_year || 3})`}
                </span>
              </button>

              {/* User Identity Pill */}
              <div className="flex items-center gap-2.5 pl-2 border-l border-[var(--border-subtle)]">
                <div
                  className="w-7 h-7 rounded-full bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--accent-primary)] font-bold text-xs shrink-0"
                  aria-hidden="true"
                >
                  {user.full_name?.charAt(0) || "U"}
                </div>
                <div className="text-left hidden md:block">
                  <p className="text-xs font-semibold text-[var(--text-primary)] leading-tight truncate max-w-[120px]">
                    {user.full_name}
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)] leading-tight">
                    {branch} {year ? `• ${year}` : ""}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleLogout}
                  className="p-1.5 text-[var(--text-muted)] hover:text-[var(--status-error-text)] hover:bg-[var(--status-error-bg)] rounded-md transition ml-1 focus-visible:outline-none"
                  title="Sign out"
                  aria-label="Sign out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Mobile menu controls */}
            <div className="lg:hidden flex items-center gap-2">
              <button
                type="button"
                onClick={toggleTheme}
                className="p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)] rounded-md border border-[var(--border-subtle)]"
                aria-label="Toggle Theme"
              >
                {resolvedTheme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
              <button
                type="button"
                onClick={() => setIsDemoModalOpen(true)}
                className="p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)] rounded-md border border-[var(--border-subtle)]"
                title="Switch role"
                aria-label="Switch Role"
              >
                <ArrowRightLeft className="w-4 h-4 text-[var(--accent-primary)]" />
              </button>
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)] rounded-md border border-[var(--border-subtle)]"
                aria-label={isMobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
                aria-expanded={isMobileMenuOpen}
              >
                {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>

          </div>
        </div>

        {/* Mobile Dropdown */}
        {isMobileMenuOpen && (
          <div className="lg:hidden px-4 pt-2 pb-4 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] space-y-1 animate-in slide-in-from-top-2 duration-150">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-semibold transition ${
                    isActive ? "bg-[var(--accent-primary)] text-white" : "text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {link.name}
                </Link>
              );
            })}
            <div className="pt-3 border-t border-[var(--border-subtle)] mt-2 flex items-center justify-between">
              <div className="text-xs text-[var(--text-muted)]">
                <p className="font-semibold text-[var(--text-primary)]">{user.full_name}</p>
                <p className="text-[11px] text-[var(--text-muted)]">{user.email}</p>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-xs text-[var(--status-error-text)] bg-[var(--status-error-bg)] hover:opacity-80 px-3 py-1.5 rounded-md font-semibold transition"
              >
                <LogOut className="w-3.5 h-3.5" /> Sign Out
              </button>
            </div>
          </div>
        )}
      </header>

      {/* Demo Switcher Modal */}
      <DemoSwitcherModal
        isOpen={isDemoModalOpen}
        onClose={() => setIsDemoModalOpen(false)}
      />
    </>
  );
}
