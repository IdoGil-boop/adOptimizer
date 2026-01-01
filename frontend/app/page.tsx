"use client";

import { useQuery } from "@tanstack/react-query";
import { AccountCard } from "@/components/account-card";
import { Button } from "@/components/ui/button";
import { Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";

interface Account {
  id: number;
  customer_id: string;
  descriptive_name: string | null;
  currency_code: string | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  total_ads: number;
  best_ads_count: number;
  worst_ads_count: number;
  is_active: boolean;
}

async function fetchAccounts(): Promise<Account[]> {
  const res = await fetch("http://localhost:8000/accounts");
  if (!res.ok) throw new Error("Failed to fetch accounts");
  return res.json();
}

export default function Dashboard() {
  const { data: accounts, isLoading, error, refetch } = useQuery({
    queryKey: ["accounts"],
    queryFn: fetchAccounts,
  });

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
  };

  return (
    <div className="space-y-8 w-full max-w-full overflow-x-hidden">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 w-full"
      >
        <div>
          <h1 className="text-4xl font-display font-bold tracking-tight">
            Dashboard
          </h1>
          <p className="mt-2 text-muted-foreground">
            Monitor your Google Ads accounts and ad performance
          </p>
        </div>
        <div className="flex flex-wrap gap-3 w-full sm:w-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
            className="flex-shrink-0"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Link href="/connect" className="flex-shrink-0">
            <Button size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Connect Account
            </Button>
          </Link>
        </div>
      </motion.div>

      {/* Error State */}
      {error && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="rounded-lg border border-destructive/50 bg-destructive/10 p-4"
        >
          <p className="text-sm font-medium text-destructive">
            Failed to load accounts: {error.message}
          </p>
        </motion.div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-64 rounded-lg border bg-card animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Accounts Grid */}
      {accounts && accounts.length > 0 && (
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid gap-6 md:grid-cols-2 lg:grid-cols-3"
        >
          {accounts.map((account) => (
            <motion.div key={account.id} variants={itemVariants}>
              <AccountCard account={account} />
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* Empty State */}
      {accounts && accounts.length === 0 && !isLoading && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card/50 p-12 text-center"
        >
          <div className="rounded-full bg-primary/10 p-4 mb-4">
            <Plus className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-lg font-display font-semibold mb-2">
            No accounts connected
          </h3>
          <p className="text-sm text-muted-foreground mb-6 max-w-sm">
            Connect your Google Ads account to start analyzing and optimizing your ad copy
          </p>
          <Link href="/connect">
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Connect Your First Account
            </Button>
          </Link>
        </motion.div>
      )}

      {/* Quick Stats */}
      {accounts && accounts.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="grid gap-4 grid-cols-2 md:grid-cols-4 w-full max-w-full"
        >
          <div className="metric-card">
            <div className="metric-label">Total Accounts</div>
            <div className="metric-value text-primary">{accounts.length}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Total Ads</div>
            <div className="metric-value">
              {accounts.reduce((sum, acc) => sum + acc.total_ads, 0).toLocaleString()}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Best Performers</div>
            <div className="metric-value text-accent">
              {accounts.reduce((sum, acc) => sum + acc.best_ads_count, 0).toLocaleString()}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Needs Improvement</div>
            <div className="metric-value text-destructive">
              {accounts.reduce((sum, acc) => sum + acc.worst_ads_count, 0).toLocaleString()}
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
