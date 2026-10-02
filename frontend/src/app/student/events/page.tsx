"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Event } from "@/lib/types";
import { CountdownTimer } from "@/components/CountdownTimer";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/LoadingState";
import { EmptyState } from "@/components/ui/EmptyState";
import { Alert } from "@/components/ui/Alert";
import {
  Calendar, PlayCircle,
  Search, Sparkles, BookOpen
} from "lucide-react";

export default function StudentEventsPage() {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [events, setEvents] = useState<Event[]>([]);
  const [search, setSearch] = useState("");
  const [filterTab, setFilterTab] = useState<"ALL" | "ACTIVE" | "UPCOMING" | "PAST">("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadEvents = () => {
    setLoading(true);
    setError(null);
    api.events.list()
      .then((evts) => setEvents(evts || []))
      .catch((err) => {
        console.error(err);
        setError(err.message || "Failed to load assessments.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/");
      return;
    }
    if (user) {
      loadEvents();
    }
  }, [user, isLoading, router]);

  if (isLoading || loading || !user) {
    return <LoadingState message="Fetching USAR Assessments..." className="min-h-[60vh]" />;
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Alert variant="error" title="Failed to Load Assessments" onRetry={loadEvents}>
          {error}
        </Alert>
      </div>
    );
  }

  const filteredEvents = events.filter((e) => {
    const matchesSearch =
      e.title.toLowerCase().includes(search.toLowerCase()) ||
      (e.description && e.description.toLowerCase().includes(search.toLowerCase()));

    if (!matchesSearch) return false;

    if (filterTab === "ACTIVE") return e.status === "ACTIVE";
    if (filterTab === "UPCOMING") return e.status === "UPCOMING";
    if (filterTab === "PAST") return e.status === "ENDED" || e.status === "RESULTS_RELEASED";
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg" style={{ backgroundColor: "var(--accent-subtle)", color: "var(--accent-primary)", border: "1px solid var(--border-subtle)" }}>
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
                USAR Coding Assessments
              </h1>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Departmental placement tests, monthly algorithmic rounds, and skill benchmarks
              </p>
            </div>
          </div>
        </div>

        {/* Search & Filter Tabs */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "var(--text-muted)" }} />
            <input
              type="text"
              placeholder="Search assessment..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-3 py-1.5 rounded-lg text-xs transition"
              style={{
                backgroundColor: "var(--bg-canvas)",
                border: "1px solid var(--border-subtle)",
                color: "var(--text-primary)"
              }}
            />
          </div>

          <div className="flex items-center p-1 rounded-lg text-xs" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
            {(["ALL", "ACTIVE", "UPCOMING", "PAST"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setFilterTab(tab)}
                className="px-3 py-1 rounded-md font-medium transition"
                style={{
                  backgroundColor: filterTab === tab ? "var(--accent-primary)" : "transparent",
                  color: filterTab === tab ? "#ffffff" : "var(--text-muted)",
                  fontWeight: filterTab === tab ? 600 : 400
                }}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Events Grid */}
      {filteredEvents.length === 0 ? (
        <EmptyState
          icon={Calendar}
          title="No Assessments Found"
          description={
            search
              ? "No events matched your search query."
              : "There are currently no scheduled coding assessments in this category."
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredEvents.map((evt) => {
            const isActive = evt.status === "ACTIVE";
            const isUpcoming = evt.status === "UPCOMING";
            const statusVariant = isActive ? "success" : isUpcoming ? "default" : "neutral";

            return (
              <Card
                key={evt.id}
                className="flex flex-col justify-between"
                style={{
                  borderColor: isActive ? "var(--accent-primary)" : "var(--border-subtle)"
                }}
              >
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant={statusVariant as any} size="sm" dot={isActive}>
                      {evt.status.replace("_", " ")}
                    </Badge>
                    <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
                      Target: {evt.target_branch} {evt.target_year > 0 ? `(Yr ${evt.target_year})` : ""}
                    </span>
                  </div>

                  <CardTitle className="mt-1.5">{evt.title}</CardTitle>
                  <CardDescription className="line-clamp-2">
                    {evt.description || "Official placement coding assessment."}
                  </CardDescription>

                  {isActive && (
                    <div className="pt-2">
                      <CountdownTimer endTime={evt.end_time} label="Ends In" />
                    </div>
                  )}
                </CardHeader>

                <CardContent className="space-y-3 pt-0 text-xs">
                  <div className="grid grid-cols-2 gap-2 font-mono text-[11px] p-2.5 rounded-lg" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                    <div>
                      <span className="block text-[10px]" style={{ color: "var(--text-muted)" }}>DURATION</span>
                      <span className="font-bold" style={{ color: "var(--text-primary)" }}>{evt.duration_minutes} Mins</span>
                    </div>
                    <div>
                      <span className="block text-[10px]" style={{ color: "var(--text-muted)" }}>PROBLEMS</span>
                      <span className="font-bold" style={{ color: "var(--accent-primary)" }}>
                        {evt.total_questions || evt.questions?.length || 0} Questions
                      </span>
                    </div>
                  </div>

                  <div className="space-y-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                    <div className="flex items-center justify-between">
                      <span>Start Window:</span>
                      <span className="font-mono" style={{ color: "var(--text-secondary)" }}>
                        {new Date(evt.start_time).toLocaleDateString()} {new Date(evt.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>End Window:</span>
                      <span className="font-mono" style={{ color: "var(--text-secondary)" }}>
                        {new Date(evt.end_time).toLocaleDateString()} {new Date(evt.end_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  </div>
                </CardContent>

                <CardFooter className="pt-3">
                  {isActive ? (
                    <Link href={`/student/events/${evt.id}`} className="w-full block">
                      <Button variant="primary" size="md" className="w-full" leftIcon={<PlayCircle className="w-4 h-4" />}>
                        Enter Assessment Arena
                      </Button>
                    </Link>
                  ) : isUpcoming ? (
                    <Button variant="secondary" size="md" className="w-full" disabled>
                      Starts at {new Date(evt.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </Button>
                  ) : (
                    <div className="grid grid-cols-2 gap-2 w-full">
                      <Link href={`/student/archive/${evt.id}`}>
                        <Button variant="secondary" size="sm" className="w-full" leftIcon={<BookOpen className="w-3.5 h-3.5" style={{ color: "var(--accent-primary)" }} />}>
                          Solutions
                        </Button>
                      </Link>
                      <Link href={`/student/reports`}>
                        <Button variant="outline" size="sm" className="w-full" leftIcon={<Sparkles className="w-3.5 h-3.5" style={{ color: "var(--accent-primary)" }} />}>
                          AI Report
                        </Button>
                      </Link>
                    </div>
                  )}
                </CardFooter>
              </Card>
            );
          })}
        </div>
      )}

    </div>
  );
}
