import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { PageLoader } from "./components/ui";
import { useAuth } from "./context/AuthContext";
import Companies from "./pages/Companies";
import CompanyDetail from "./pages/CompanyDetail";
import ContactDetail from "./pages/ContactDetail";
import Contacts from "./pages/Contacts";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import LoginAzureCallback from "./pages/LoginAzureCallback";
import MarketResearch from "./pages/MarketResearch";
import ResearchDetail from "./pages/ResearchDetail";
import Settings from "./pages/Settings";
import Users from "./pages/Users";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AdminRoute({ children }) {
  const { isAdmin, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!isAdmin) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/login/azure-callback" element={<LoginAzureCallback />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="companies" element={<Companies />} />
        <Route path="companies/:id" element={<CompanyDetail />} />
        <Route path="contacts" element={<Contacts />} />
        <Route path="contacts/:id" element={<ContactDetail />} />
        <Route path="apollo" element={<Navigate to="/research" replace />} />
        <Route path="research" element={<MarketResearch />} />
        <Route path="research/:id" element={<ResearchDetail />} />
        <Route
          path="settings"
          element={
            <AdminRoute>
              <Settings />
            </AdminRoute>
          }
        />
        <Route
          path="users"
          element={
            <AdminRoute>
              <Users />
            </AdminRoute>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
