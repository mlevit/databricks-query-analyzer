import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "flowbite";
import App from "./App";
import AnalyzePage from "./pages/AnalyzePage";
import ScanPage from "./pages/ScanPage";
import SqlAnalyzePage from "./pages/SqlAnalyzePage";
import TablesPage from "./pages/TablesPage";
import TrendsPage from "./pages/TrendsPage";
import WarehousesPage from "./pages/WarehousesPage";
import "./index.css";

const stored = localStorage.getItem("dqa-dark-mode");
if (stored === "true" || (!stored && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
  document.documentElement.classList.add("dark");
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<AnalyzePage />} />
          <Route path="sql" element={<SqlAnalyzePage />} />
          <Route path="scan" element={<ScanPage />} />
          <Route path="trends" element={<TrendsPage />} />
          <Route path="tables" element={<TablesPage />} />
          <Route path="warehouses" element={<WarehousesPage />} />
          <Route path="*" element={<AnalyzePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
