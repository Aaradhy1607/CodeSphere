"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { User } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Alert } from "@/components/ui/Alert";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableContainer } from "@/components/ui/Table";
import { useToast } from "@/components/ui/Toast";
import {
  Users, UserPlus, Search, Eye, Trash2
} from "lucide-react";

export default function AdminStudentsPage() {
  const router = useRouter();
  const { user, isAdmin, isLoading } = useAuth();
  const toast = useToast();

  const [students, setStudents] = useState<User[]>([]);
  const [branchFilter, setBranchFilter] = useState("ALL");
  const [yearFilter, setYearFilter] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [selectedStudentHistory, setSelectedStudentHistory] = useState<any>(null);

  // Student to delete state
  const [studentToDelete, setStudentToDelete] = useState<User | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Form State
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [enrollmentNo, setEnrollmentNo] = useState("");
  const [branch, setBranch] = useState("AIML");
  const [academicYear, setAcademicYear] = useState(3);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadStudents = () => {
    setLoading(true);
    setError(null);
    api.students.list(branchFilter, yearFilter, search)
      .then(setStudents)
      .catch((err) => {
        console.error(err);
        setError(err.message || "Failed to load students roster.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!isLoading && (!user || !isAdmin)) {
      router.push("/");
      return;
    }
    if (user && isAdmin) {
      loadStudents();
    }
  }, [user, isAdmin, isLoading, branchFilter, yearFilter, router]);

  const handleAddStudent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !enrollmentNo) {
      toast.error("Name, email, and enrollment number are required");
      return;
    }

    setIsSubmitting(true);
    try {
      await api.students.create(name, email, enrollmentNo, branch, academicYear);
      setIsAddModalOpen(false);
      setName("");
      setEmail("");
      setEnrollmentNo("");
      toast.success("Student added to authorized whitelist");
      loadStudents();
    } catch (err: any) {
      toast.error(err.message || "Failed to whitelist student");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleStatus = async (studentId: number, currentActive: boolean) => {
    try {
      await api.students.toggleStatus(studentId, !currentActive);
      toast.success(!currentActive ? "Student account activated" : "Student account deactivated");
      loadStudents();
    } catch (err: any) {
      toast.error(err.message || "Failed to toggle status");
    }
  };

  const handleViewHistory = async (studentId: number) => {
    try {
      const hist = await api.students.getHistory(studentId);
      setSelectedStudentHistory(hist);
    } catch (err: any) {
      toast.error(err.message || "Failed to load student transcript history");
    }
  };

  const handleDeleteStudent = async () => {
    if (!studentToDelete) return;
    setIsDeleting(true);
    try {
      await api.students.delete(studentToDelete.id);
      toast.success("Student record deleted");
      setStudentToDelete(null);
      loadStudents();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete student.");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg" style={{ backgroundColor: "var(--accent-subtle)", color: "var(--accent-primary)", border: "1px solid var(--border-subtle)" }}>
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
                Student Roster & Profiles
              </h1>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Manage university student registrations, department eligibility, and individual assessment transcripts
              </p>
            </div>
          </div>
        </div>

        <Button
          variant="primary"
          size="sm"
          onClick={() => setIsAddModalOpen(true)}
          leftIcon={<UserPlus className="w-4 h-4" />}
        >
          Whitelist Student
        </Button>
      </div>

      {/* Filter Toolbar */}
      <Card className="p-3 sm:p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex-1 relative max-w-md">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "var(--text-muted)" }} />
            <input
              type="text"
              placeholder="Search by name, email, enrollment..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadStudents()}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg text-xs transition"
              style={{
                backgroundColor: "var(--bg-canvas)",
                border: "1px solid var(--border-subtle)",
                color: "var(--text-primary)"
              }}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Branch:</span>
              <select
                value={branchFilter}
                onChange={(e) => setBranchFilter(e.target.value)}
                className="text-xs rounded-lg px-2.5 py-1.5 cursor-pointer"
                style={{
                  backgroundColor: "var(--bg-canvas)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)"
                }}
              >
                <option value="ALL">All Branches</option>
                <option value="AIML">AIML</option>
                <option value="AIDS">AIDS</option>
                <option value="IIOT">IIOT</option>
                <option value="AR">AR</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Year:</span>
              <select
                value={yearFilter}
                onChange={(e) => setYearFilter(Number(e.target.value))}
                className="text-xs rounded-lg px-2.5 py-1.5 cursor-pointer"
                style={{
                  backgroundColor: "var(--bg-canvas)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)"
                }}
              >
                <option value={0}>All Years</option>
                <option value={1}>1st Year</option>
                <option value={2}>2nd Year</option>
                <option value={3}>3rd Year</option>
                <option value={4}>4th Year</option>
              </select>
            </div>
          </div>
        </div>
      </Card>

      {/* Roster Table */}
      {loading ? (
        <LoadingState message="Fetching Student Roster..." className="min-h-[40vh]" />
      ) : error ? (
        <Alert variant="error" title="Failed to Load Students" onRetry={loadStudents}>
          {error}
        </Alert>
      ) : students.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No Students Found"
          description={search ? "No students matched your search criteria." : "No student records exist in the database."}
          actionLabel="Whitelist Student"
          onAction={() => setIsAddModalOpen(true)}
        />
      ) : (
        <TableContainer>
          <Table>
            <TableHeader>
              <TableRow interactive={false}>
                <TableHead>Student</TableHead>
                <TableHead>Enrollment No</TableHead>
                <TableHead>Department</TableHead>
                <TableHead>Academic Year</TableHead>
                <TableHead>Readiness</TableHead>
                <TableHead>Account Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {students.map((stu) => {
                const profile = stu.student_profile;
                const branchVariant =
                  profile?.branch === "AIML" ? "aiml" :
                  profile?.branch === "AIDS" ? "aids" :
                  profile?.branch === "IIOT" ? "iiot" :
                  profile?.branch === "AR" ? "ar" : "neutral";

                const readinessVariant =
                  profile?.placement_readiness_rating === "Ready" ? "success" :
                  profile?.placement_readiness_rating === "High Potential" ? "default" :
                  profile?.placement_readiness_rating === "Needs Focus" ? "destructive" : "warning";

                return (
                  <TableRow key={stu.id}>
                    <TableCell>
                      <div>
                        <span className="font-semibold block text-xs sm:text-sm" style={{ color: "var(--text-primary)" }}>{stu.full_name}</span>
                        <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>{stu.email}</span>
                      </div>
                    </TableCell>

                    <TableCell className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                      {profile?.enrollment_no || "N/A"}
                    </TableCell>

                    <TableCell>
                      <Badge variant={branchVariant as any} size="sm">
                        {profile?.branch || "USAR"}
                      </Badge>
                    </TableCell>

                    <TableCell className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                      Year {profile?.academic_year || 3}
                    </TableCell>

                    <TableCell>
                      <Badge variant={readinessVariant as any} size="sm">
                        {profile?.placement_readiness_rating || "Developing"}
                      </Badge>
                    </TableCell>

                    <TableCell>
                      <button
                        type="button"
                        onClick={() => handleToggleStatus(stu.id, stu.is_active)}
                        className="text-[11px] font-semibold px-2 py-0.5 rounded transition"
                        style={{
                          backgroundColor: stu.is_active ? "var(--color-success-subtle)" : "var(--bg-canvas)",
                          color: stu.is_active ? "var(--color-success)" : "var(--text-muted)",
                          border: `1px solid ${stu.is_active ? "var(--color-success)" : "var(--border-subtle)"}`
                        }}
                      >
                        {stu.is_active ? "Active" : "Disabled"}
                      </button>
                    </TableCell>

                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleViewHistory(stu.id)}
                          title="View transcript history"
                          aria-label={`View history for ${stu.full_name}`}
                        >
                          <Eye className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setStudentToDelete(stu)}
                          title="Delete student"
                          aria-label={`Delete student ${stu.full_name}`}
                        >
                          <Trash2 className="w-4 h-4" style={{ color: "var(--color-danger)" }} />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Whitelist New Student Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Whitelist New Student Candidate"
        description="Add an eligible student to the USAR placement and coding portal."
        size="md"
      >
        <form onSubmit={handleAddStudent} className="space-y-3.5 text-xs">
          <Input
            label="Full Name *"
            required
            placeholder="e.g. Diya Sengupta"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          <Input
            label="University Email *"
            type="email"
            required
            placeholder="e.g. rollno@std.ggsipu.ac.in"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <Input
            label="Enrollment Number *"
            required
            placeholder="e.g. 01819011922"
            value={enrollmentNo}
            onChange={(e) => setEnrollmentNo(e.target.value)}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Select
              label="Department / Branch *"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
            >
              <option value="AIML">Artificial Intelligence & ML (AIML)</option>
              <option value="AIDS">Artificial Intelligence & DS (AIDS)</option>
              <option value="IIOT">Industrial IoT (IIOT)</option>
              <option value="AR">Automation & Robotics (AR)</option>
            </Select>

            <Select
              label="Academic Year *"
              value={academicYear}
              onChange={(e) => setAcademicYear(Number(e.target.value))}
            >
              <option value={1}>1st Year</option>
              <option value={2}>2nd Year</option>
              <option value={3}>3rd Year (Pre-Placement)</option>
              <option value={4}>4th Year (Placement Active)</option>
            </Select>
          </div>

          <div className="flex items-center justify-end gap-2 pt-3" style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <Button variant="outline" size="sm" onClick={() => setIsAddModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" isLoading={isSubmitting}>
              Add to Whitelist
            </Button>
          </div>
        </form>
      </Modal>

      {/* Student History & Transcripts Modal */}
      {selectedStudentHistory && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedStudentHistory(null)}
          title={`Candidate Transcript: ${selectedStudentHistory.student?.full_name}`}
          description={`Enrollment: ${selectedStudentHistory.student?.student_profile?.enrollment_no || "N/A"} • ${selectedStudentHistory.student?.student_profile?.branch} Year ${selectedStudentHistory.student?.student_profile?.academic_year}`}
          size="lg"
        >
          <div className="space-y-4 text-xs">
            {/* Aggregate Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div className="p-2.5 rounded-lg text-center" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                <span className="text-[10px] uppercase font-mono block" style={{ color: "var(--text-muted)" }}>Lifetime Score</span>
                <span className="font-mono font-bold text-sm" style={{ color: "var(--color-success)" }}>
                  {selectedStudentHistory.student?.student_profile?.total_lifetime_score || 0} pts
                </span>
              </div>
              <div className="p-2.5 rounded-lg text-center" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                <span className="text-[10px] uppercase font-mono block" style={{ color: "var(--text-muted)" }}>Solved Problems</span>
                <span className="font-mono font-bold text-sm" style={{ color: "var(--accent-primary)" }}>
                  {selectedStudentHistory.student?.student_profile?.total_problems_solved || 0}
                </span>
              </div>
              <div className="p-2.5 rounded-lg text-center" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                <span className="text-[10px] uppercase font-mono block" style={{ color: "var(--text-muted)" }}>Events Participated</span>
                <span className="font-mono font-bold text-sm" style={{ color: "var(--text-primary)" }}>
                  {selectedStudentHistory.student?.student_profile?.total_events_participated || 0}
                </span>
              </div>
              <div className="p-2.5 rounded-lg text-center" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                <span className="text-[10px] uppercase font-mono block" style={{ color: "var(--text-muted)" }}>Readiness</span>
                <span className="font-mono font-bold text-sm" style={{ color: "var(--color-warning)" }}>
                  {selectedStudentHistory.student?.student_profile?.placement_readiness_rating || "Developing"}
                </span>
              </div>
            </div>

            {/* Submission Log */}
            <div className="space-y-2">
              <h4 className="font-bold uppercase tracking-wider text-[11px]" style={{ color: "var(--text-primary)" }}>Assessment Submissions:</h4>
              {selectedStudentHistory.submissions && selectedStudentHistory.submissions.length > 0 ? (
                <div className="space-y-1.5 max-h-56 overflow-y-auto">
                  {selectedStudentHistory.submissions.map((sub: any) => (
                    <div
                      key={sub.id}
                      className="p-2.5 rounded-lg flex items-center justify-between text-xs"
                      style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}
                    >
                      <div className="truncate">
                        <span className="font-semibold block truncate" style={{ color: "var(--text-primary)" }}>{sub.question_title || `Problem #${sub.question_id}`}</span>
                        <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
                          {sub.language} • {new Date(sub.submitted_at).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="text-right shrink-0">
                        <Badge variant={sub.verdict === "Accepted" ? "success" : "destructive"} size="sm">
                          {sub.verdict}
                        </Badge>
                        <span className="font-mono text-[11px] block mt-0.5" style={{ color: "var(--text-secondary)" }}>{sub.score} pts</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs py-3 text-center" style={{ color: "var(--text-muted)" }}>No submissions recorded for this student.</p>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={studentToDelete !== null}
        onClose={() => setStudentToDelete(null)}
        onConfirm={handleDeleteStudent}
        title="Remove Student Record"
        message={`Are you sure you want to remove ${studentToDelete?.full_name} (${studentToDelete?.email}) from the platform?`}
        confirmText="Remove Record"
        variant="destructive"
        isLoading={isDeleting}
      />

    </div>
  );
}
