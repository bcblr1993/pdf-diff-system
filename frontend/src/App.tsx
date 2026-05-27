import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Login from "@/pages/Login";
import ComparisonList from "@/pages/ComparisonList";
import ComparisonNew from "@/pages/ComparisonNew";
import ComparisonDetail from "@/pages/ComparisonDetail";
import BatchList from "@/pages/BatchList";
import BatchDetail from "@/pages/BatchDetail";
import Integrations from "@/pages/Integrations";
import AppShell from "@/components/AppShell";
import RequireAuth from "@/components/RequireAuth";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RequireAuth />}>
            <Route element={<AppShell />}>
              <Route path="/" element={<ComparisonList />} />
              <Route path="/new" element={<ComparisonNew />} />
              <Route path="/comparisons/:id" element={<ComparisonDetail />} />
              <Route path="/batches" element={<BatchList />} />
              <Route path="/batches/:id" element={<BatchDetail />} />
              <Route path="/integrations" element={<Integrations />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
