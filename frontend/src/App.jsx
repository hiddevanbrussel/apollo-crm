import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { PageLoader } from "./components/ui";
import { useAuth } from "./context/AuthContext";
import ApolloSearch from "./pages/ApolloSearch";
import CompanyDetail from "./pages/CompanyDetail";
import Companies from "./pages/Companies";
import ContactDetail from "./pages/ContactDetail";
import Contacts from "./pages/Contacts";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import MarketResearch from "./pages/MarketResearch";
import Settings from "./pages/Settings";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
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
        <Route path="apollo" element={<ApolloSearch />} />
        <Route path="research" element={<MarketResearch />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
