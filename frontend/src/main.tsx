import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import { ConfirmProvider } from "./components/ConfirmDialog";
import { ToastProvider } from "./components/toast";
import "./styles/global.css";

const queryClient = new QueryClient();

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ConfirmProvider>
          <App />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
