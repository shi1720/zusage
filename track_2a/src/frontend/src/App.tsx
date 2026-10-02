import { lazy, Suspense } from "react";

import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth";
import { Shell } from "./components/Shell";
import { Spinner } from "./components/ui";
import { useI18n } from "./lib/i18n";
const WorkspacePage = lazy(() => import("./pages/WorkspacePage"));
const ApplicationsPage = lazy(() => import("./pages/ApplicationsPage"));
const ClassPage = lazy(() => import("./pages/ClassPage"));
const InterviewPage = lazy(() => import("./pages/InterviewPage"));
const LandingPage = lazy(() => import("./pages/LandingPage"));
const PracticePage = lazy(() => import("./pages/PracticePage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const ProgressPage = lazy(() => import("./pages/ProgressPage"));
const ReportPage = lazy(() => import("./pages/ReportPage"));
const StudentPage = lazy(() => import("./pages/StudentPage"));
const TodayPage = lazy(() => import("./pages/TodayPage"));

export default function App() {
  const { user, ready, error } = useAuth();
  const { t } = useI18n();

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center gap-3 text-ink-2">
        <Spinner /> Zusage…
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-2 px-6 text-center">
        <p className="font-display text-lg font-bold">{t("Can't reach the Zusage server")}</p>
        <p className="max-w-md text-sm text-ink-2">{error}</p>
      </div>
    );
  }
  if (!user) return <LandingPage />;

  const teacher = user.role !== "student";
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center"><Spinner /></div>}>
    <Routes>
      {/* focus mode - no sidebar */}
      <Route path="/interview/:id" element={<InterviewPage />} />
      <Route
        path="*"
        element={
          <Shell>
            <Routes>
              <Route path="/" element={teacher ? <ClassPage /> : <TodayPage />} />
              <Route path="/practice" element={<PracticePage />} />
              <Route path="/report/:id" element={<ReportPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              {!teacher && <Route path="/applications" element={<ApplicationsPage />} />}
              {!teacher && ["/outreach", "/nudges", "/import", "/analytics"].map(path=><Route key={path} path={path} element={<WorkspacePage/>}/>)}
              {!teacher && <Route path="/progress" element={<ProgressPage />} />}
              {teacher && <Route path="/classes/:classId" element={<ClassPage />} />}
              {teacher && <Route path="/classes/:classId/students/:studentId" element={<StudentPage />} />}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Shell>
        }
      />
    </Routes>
    </Suspense>
  );
}
