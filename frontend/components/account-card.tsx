"use client";

import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { RefreshCw, TrendingUp, TrendingDown, AlertCircle, BarChart3 } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { formatDistanceToNow } from "date-fns";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "./ui/use-toast";

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

interface AccountCardProps {
  account: Account;
}

export function AccountCard({ account }: AccountCardProps) {
  const syncStatus = account.last_sync_status?.toLowerCase();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const getStatusBadge = () => {
    switch (syncStatus) {
      case "success":
        return <Badge variant="success">✓ Synced</Badge>;
      case "running":
        return <Badge variant="default">⏳ Syncing</Badge>;
      case "failed":
        return <Badge variant="destructive">✗ Failed</Badge>;
      default:
        return <Badge variant="outline">○ Pending</Badge>;
    }
  };

  const syncMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`http://localhost:8000/accounts/${account.id}/sync`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Sync failed");
      return res.json();
    },
    onSuccess: () => {
      toast({
        title: "Sync Started",
        description: "Account sync has been initiated",
      });
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
    onError: (error: Error) => {
      toast({
        title: "Sync Failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const scoreMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`http://localhost:8000/accounts/${account.id}/score`, {
        method: "POST",
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Scoring failed");
      }
      return res.json();
    },
    onSuccess: (data) => {
      toast({
        title: "Scoring Complete",
        description: `Classified ${data.best_count || 0} best, ${data.worst_count || 0} worst ads`,
      });
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["ads"] });
    },
    onError: (error: Error) => {
      toast({
        title: "Scoring Failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleSync = () => {
    syncMutation.mutate();
  };

  const handleScore = () => {
    scoreMutation.mutate();
  };

  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="group relative overflow-hidden rounded-lg border bg-card p-6 shadow-sm transition-all hover:shadow-lg hover:shadow-primary/5 w-full max-w-full"
    >
      {/* Decorative gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-accent/5 opacity-0 group-hover:opacity-100 transition-opacity" />

      <div className="relative space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3 className="font-display text-lg font-semibold truncate">
              {account.descriptive_name || "Unnamed Account"}
            </h3>
            <p className="font-mono text-sm text-muted-foreground truncate">
              {account.customer_id}
            </p>
          </div>
          <div className="flex-shrink-0">{getStatusBadge()}</div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1">
            <div className="text-xs font-mono uppercase text-muted-foreground">
              Total
            </div>
            <div className="font-mono text-2xl font-bold">
              {account.total_ads}
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-xs font-mono uppercase text-muted-foreground flex items-center gap-1">
              <TrendingUp className="h-3 w-3" />
              Best
            </div>
            <div className="font-mono text-2xl font-bold text-accent">
              {account.best_ads_count}
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-xs font-mono uppercase text-muted-foreground flex items-center gap-1">
              <TrendingDown className="h-3 w-3" />
              Worst
            </div>
            <div className="font-mono text-2xl font-bold text-destructive">
              {account.worst_ads_count}
            </div>
          </div>
        </div>

        {/* Last Sync Info */}
        {account.last_sync_at && (
          <div className="text-xs text-muted-foreground">
            Last synced{" "}
            {formatDistanceToNow(new Date(account.last_sync_at), {
              addSuffix: true,
            })}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Link href={`/ads?account_id=${account.id}`} className="flex-1">
            <Button variant="outline" size="sm" className="w-full">
              View Ads
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleSync}
            disabled={syncStatus === "running" || syncMutation.isPending}
            title="Sync account data"
          >
            <RefreshCw
              className={`h-4 w-4 ${syncStatus === "running" || syncMutation.isPending ? "animate-spin" : ""}`}
            />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleScore}
            disabled={scoreMutation.isPending}
            title="Recalculate ad scoring"
          >
            <BarChart3
              className={`h-4 w-4 ${scoreMutation.isPending ? "animate-pulse" : ""}`}
            />
          </Button>
        </div>

        {/* Warning for no data */}
        {account.total_ads === 0 && (
          <div className="flex items-center gap-2 rounded-md border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-600 dark:text-amber-400">
            <AlertCircle className="h-4 w-4" />
            <span>No ads found. Try syncing this account.</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
