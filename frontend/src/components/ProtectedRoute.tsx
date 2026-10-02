"use client";

import React, { ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { UserRole, Permission } from "@/lib/types";
import { ShieldAlert, ArrowLeft, Lock } from "lucide-react";
import Link from "next/link";

interface ProtectedRouteProps {
  children: ReactNode;
  requiredRole?: UserRole | UserRole[];
  requiredPermission?: Permission | Permission[];
}

export function ProtectedRoute({
  children,
  requiredRole,
  requiredPermission
}: ProtectedRouteProps) {
  const { user, isLoading, hasRole, hasPermission } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  React.useEffect(() => {
    if (!isLoading && !user) {
      const returnUrl = encodeURIComponent(pathname);
      router.push(`/login?returnUrl=${returnUrl}`);
    }
  }, [user, isLoading, router, pathname]);

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center space-y-4">
        <div className="w-10 h-10 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin dark:border-indigo-400" />
        <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">
          Verifying security credentials...
        </p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Check Role authorization
  if (requiredRole && !hasRole(requiredRole)) {
    const rolesRequired = Array.isArray(requiredRole) ? requiredRole.join(", ") : requiredRole;
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-white dark:bg-slate-900 border border-red-200 dark:border-red-900/50 rounded-2xl p-8 text-center shadow-lg">
          <div className="w-14 h-14 bg-red-100 dark:bg-red-950/50 text-red-600 dark:text-red-400 rounded-2xl flex items-center justify-center mx-auto mb-5 border border-red-200 dark:border-red-900/30">
            <Lock className="w-7 h-7" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
            Access Restricted
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-6 leading-relaxed">
            Your current role (<span className="font-semibold text-slate-800 dark:text-slate-200">{user.role}</span>) does not have authorization to view this administrative resource. Required role: <span className="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded text-red-600 dark:text-red-400">{rolesRequired}</span>.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100 transition-colors shadow-sm"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Return to Dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Check Permission authorization
  if (requiredPermission) {
    const perms = Array.isArray(requiredPermission) ? requiredPermission : [requiredPermission];
    const hasAll = perms.every((p) => hasPermission(p));
    if (!hasAll) {
      return (
        <div className="min-h-[70vh] flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/50 rounded-2xl p-8 text-center shadow-lg">
            <div className="w-14 h-14 bg-amber-100 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 rounded-2xl flex items-center justify-center mx-auto mb-5 border border-amber-200 dark:border-amber-900/30">
              <ShieldAlert className="w-7 h-7" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
              Insufficient Permissions
            </h1>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-6 leading-relaxed">
              Your account lacks the specific permission (<span className="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded text-amber-600 dark:text-amber-400">{perms.join(", ")}</span>) required to perform this action. Contact University Administration.
            </p>
            <div className="flex justify-center">
              <Link
                href="/dashboard"
                className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100 transition-colors shadow-sm"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Return to Dashboard
              </Link>
            </div>
          </div>
        </div>
      );
    }
  }

  return <>{children}</>;
}
