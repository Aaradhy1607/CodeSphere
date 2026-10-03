"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { useTheme } from "@/lib/themeContext";
import {
  Code2, LayoutDashboard, Calendar, Trophy, Sparkles,
  Users, BarChart3, Database, LogOut, Menu, X,
  Sun, Moon, Shield
} from "lucide-react";

export function Navbar() {
  const { user, logout, isAdmin, isSuperAdmin } = useAuth();
  const { resolvedTheme, toggleTheme } = useTheme();
  const pathname = usePathname();
  const router = useRouter();
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
    { name: "Command", href: "/admin/dashboard", icon: LayoutDashboard },
    { name: "Assessments", href: "/admin/assessments", icon: Shield },
    { name: "Contests", href: "/admin/events", icon: Calendar },
    { name: "Questions", href: "/admin/questions", icon: Database },
    { name: "AI Lab", href: "/admin/ai-generator", icon: Sparkles },
    { name: "Roster", href: "/admin/students", icon: Users },
    { name: "Analytics", href: "/admin/analytics", icon: BarChart3 },
    { name: "Leaderboard", href: "/admin/leaderboards", icon: Trophy },
  ];

  const navLinks = isAdmin ? adminLinks : studentLinks;

  const handleLogout = async () => {
    setIsMobileMenuOpen(false);
    await logout();
    router.replace("/");
  };

  const branch = user.student_profile?.branch || (isAdmin ? "PLACEMENT CELL" : "USAR");
  const year = user.student_profile?.academic_year ? `Yr ${user.student_profile.academic_year}` : "";
  const roleLabel = isSuperAdmin ? "Super Admin" : isAdmin ? "Admin" : (user.role || "Student");

  return (
    <header className="sticky top-0 z-50 w-full bg-[var(--bg-surface)]/95 backdrop-blur-md border-b border-[var(--border-subtle)] transition-colors">
      <div className="w-full px-2 sm:px-4 lg:px-6">
        <div className="flex items-center justify-between h-14 sm:h-16 gap-1 sm:gap-3">
          
          {/* Left Side: Brand Logo + Nav Links */}
          <div className="flex items-center gap-2 xl:gap-4 min-w-0">
            <Link
              href={isAdmin ? "/admin/dashboard" : "/student/dashboard"}
              className="flex items-center gap-2 group focus-visible:outline-none rounded-md p-1 shrink-0"
              aria-label="CodeSphere Home"
            >
              <div className="w-8 h-8 rounded-md bg-[var(--accent-primary)] flex items-center justify-center text-white font-bold shadow-sm shrink-0">
                <Code2 className="w-5 h-5" />
              </div>
              <div className="hidden sm:block shrink-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-sm tracking-tight text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] transition">
                    CodeSphere
                  </span>
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-[var(--accent-subtle)] text-[var(--accent-text)] border border-[var(--accent-border)]">
                    USAR
                  </span>
                </div>
              </div>
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden xl:flex items-center gap-1 min-w-0" aria-label="Main Navigation">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const isActive = pathname === link.href || (pathname.startsWith(`${link.href}/`) && link.href !== "/admin/events" && link.href !== "/student/events");
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`flex items-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-medium transition-colors focus-visible:outline-none shrink-0 ${
                      isActive
                        ? "bg-[var(--accent-primary)] text-white shadow-sm font-semibold"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]"
                    }`}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{link.name}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Right Side: Theme, User Identity & Prominent Logout */}
          <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
            {/* Theme Toggle Button */}
            <button
              type="button"
              onClick={toggleTheme}
              className="p-1.5 rounded-md bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)] transition focus-visible:outline-none shrink-0 cursor-pointer"
              title={`Switch to ${resolvedTheme === "dark" ? "Light" : "Dark"} mode`}
              aria-label="Toggle Theme"
            >
              {resolvedTheme === "dark" ? (
                <Sun className="w-4 h-4 text-[var(--status-warning-text)]" />
              ) : (
                <Moon className="w-4 h-4 text-[var(--text-primary)]" />
              )}
            </button>

            {/* User Profile Info Pill */}
            <div className="flex items-center gap-1.5 sm:gap-2 pl-1.5 sm:pl-2 border-l border-[var(--border-subtle)] shrink-0">
              <div
                className="w-7 h-7 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent-border)] flex items-center justify-center text-[var(--accent-primary)] font-bold text-xs shrink-0 shadow-xs"
                aria-hidden="true"
              >
                {user.full_name?.charAt(0) || "U"}
              </div>
              <div className="text-left hidden md:block max-w-[110px] lg:max-w-[150px] shrink-0">
                <p className="text-xs font-semibold text-[var(--text-primary)] leading-tight truncate">
                  {user.full_name}
                </p>
                <p className="text-[10px] text-[var(--text-muted)] leading-tight truncate">
                  {roleLabel} {branch && branch !== "USAR" ? `• ${branch}` : ""}
                </p>
              </div>
            </div>

            {/* High-Visibility Sign Out Button (Always visible on all screen sizes) */}
            <button
              type="button"
              onClick={handleLogout}
              className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 text-xs font-semibold text-red-600 dark:text-red-400 bg-red-50 hover:bg-red-100 dark:bg-red-950/40 dark:hover:bg-red-900/60 border border-red-200 dark:border-red-900/50 rounded-md transition focus-visible:outline-none shadow-xs cursor-pointer shrink-0"
              title="Sign out of your session"
              aria-label="Sign out"
            >
              <LogOut className="w-3.5 h-3.5 shrink-0" />
              <span className="font-semibold">Sign Out</span>
            </button>

            {/* Mobile / Compact menu hamburger toggle (< xl) */}
            <div className="xl:hidden flex items-center shrink-0">
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="p-1.5 text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)] rounded-md border border-[var(--border-subtle)] cursor-pointer"
                aria-label={isMobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
                aria-expanded={isMobileMenuOpen}
              >
                {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>

        </div>
      </div>

      {/* Mobile / Tablet Dropdown Menu */}
      {isMobileMenuOpen && (
        <div className="xl:hidden px-4 pt-2 pb-4 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] space-y-1 animate-in slide-in-from-top-2 duration-150 shadow-lg">
          <p className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] px-3 py-1">
            Navigation
          </p>
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
              className="flex items-center gap-1.5 text-xs font-semibold text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 hover:bg-red-100 dark:hover:bg-red-900/60 border border-red-200 dark:border-red-900/50 px-3 py-1.5 rounded-md transition cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" /> Sign Out
            </button>
          </div>
        </div>
      )}
    </header>
  );
}
