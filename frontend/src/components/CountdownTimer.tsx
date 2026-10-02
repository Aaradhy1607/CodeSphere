"use client";

import React, { useState, useEffect } from "react";
import { Clock, AlertTriangle } from "lucide-react";

interface CountdownTimerProps {
  endTime: string;
  onExpire?: () => void;
  label?: string;
}

export function CountdownTimer({ endTime, onExpire, label = "Time Remaining" }: CountdownTimerProps) {
  const [timeLeft, setTimeLeft] = useState<{
    hours: number;
    minutes: number;
    seconds: number;
    isUrgent: boolean;
    isExpired: boolean;
  }>({
    hours: 0,
    minutes: 0,
    seconds: 0,
    isUrgent: false,
    isExpired: false,
  });

  useEffect(() => {
    const calculateTime = () => {
      const target = new Date(endTime).getTime();
      const now = new Date().getTime();
      const diff = target - now;

      if (diff <= 0) {
        setTimeLeft({
          hours: 0,
          minutes: 0,
          seconds: 0,
          isUrgent: false,
          isExpired: true,
        });
        if (onExpire) onExpire();
        return;
      }

      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      const isUrgent = diff <= 15 * 60 * 1000; // < 15 minutes

      setTimeLeft({ hours, minutes, seconds, isUrgent, isExpired: false });
    };

    calculateTime();
    const interval = setInterval(calculateTime, 1000);
    return () => clearInterval(interval);
  }, [endTime, onExpire]);

  const pad = (n: number) => String(n).padStart(2, "0");

  if (timeLeft.isExpired) {
    return (
      <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-semibold">
        <Clock className="w-3.5 h-3.5" />
        <span>Assessment Concluded</span>
      </div>
    );
  }

  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
        timeLeft.isUrgent
          ? "bg-rose-950/40 border-rose-500/50 text-rose-300 font-semibold"
          : "bg-slate-900 border-slate-700 text-slate-200 font-medium"
      }`}
    >
      {timeLeft.isUrgent ? (
        <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
      ) : (
        <Clock className="w-3.5 h-3.5 text-blue-400 shrink-0" />
      )}
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] text-slate-400 hidden sm:inline">{label}:</span>
        <span className="font-mono font-bold text-xs sm:text-sm text-white tracking-wider">
          {pad(timeLeft.hours)}:{pad(timeLeft.minutes)}:{pad(timeLeft.seconds)}
        </span>
      </div>
    </div>
  );
}
