import { Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import PartsLibrary from "./pages/PartsLibrary";
import Settings from "./pages/Settings";

function NavItem({ to, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-4 py-2 rounded text-sm font-medium transition-colors ${
          isActive
            ? "bg-blue-600 text-white"
            : "text-slate-300 hover:bg-slate-700"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Top navigation */}
      <nav className="bg-slate-800 border-b border-slate-700 px-6 py-3 flex items-center gap-4">
        <span className="text-white font-bold text-lg mr-6">
          Kaplama Sistemi
        </span>
        <NavItem to="/" label="Dashboard" />
        <NavItem to="/parts" label="Parça Kütüphanesi" />
        <NavItem to="/settings" label="Ayarlar" />
      </nav>

      {/* Page content */}
      <main className="flex-1 p-4">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/parts" element={<PartsLibrary />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
