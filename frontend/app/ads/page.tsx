"use client";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowUpRight,
  ChevronRight,
  Filter,
  Loader2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";

type Account = {
  id: number;
  customer_id: string;
  customer_name: string;
  sync_status: string;
  last_synced_at: string | null;
};

type Ad = {
  id: number;
  ad_id: string;
  ad_type: string;
  headlines: string[];
  descriptions: string[];
  bucket: "best" | "worst" | "unknown";
  metrics_90d: {
    impressions: number;
    clicks: number;
    ctr: number;
    conversions: number;
    cvr: number;
    cost_micros: number;
    cost_per_conversion_micros: number | null;
  };
};

const API_BASE = "http://localhost:8000";

export default function AdsPage() {
  const searchParams = useSearchParams();
  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [bucketFilter, setBucketFilter] = useState<"all" | "best" | "worst">("all");

  // Fetch accounts
  const { data: accounts, isLoading: accountsLoading } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/accounts/`);
      if (!res.ok) throw new Error("Failed to fetch accounts");
      return res.json();
    },
  });

  // Load selected account from localStorage or URL parameter
  useEffect(() => {
    const accountIdFromUrl = searchParams.get("account_id");
    const cachedAccountId = localStorage.getItem("selectedAccountId");
    
    if (accountIdFromUrl) {
      setSelectedAccountId(accountIdFromUrl);
      localStorage.setItem("selectedAccountId", accountIdFromUrl);
    } else if (cachedAccountId && !selectedAccountId) {
      setSelectedAccountId(cachedAccountId);
    }
  }, [searchParams, selectedAccountId]);

  // Save selected account to localStorage when it changes
  useEffect(() => {
    if (selectedAccountId) {
      localStorage.setItem("selectedAccountId", selectedAccountId);
    }
  }, [selectedAccountId]);

  // Clear cached account if it's no longer in the accounts list (disconnected)
  useEffect(() => {
    if (accounts && selectedAccountId) {
      const accountExists = accounts.some(
        (acc) => String(acc.id) === selectedAccountId
      );
      if (!accountExists) {
        setSelectedAccountId("");
        localStorage.removeItem("selectedAccountId");
      }
    }
  }, [accounts, selectedAccountId]);

  // Fetch ads for selected account
  const {
    data: ads,
    isLoading: adsLoading,
    error: adsError,
  } = useQuery<Ad[]>({
    queryKey: ["ads", selectedAccountId, bucketFilter],
    queryFn: async () => {
      if (!selectedAccountId) return [];
      const params = new URLSearchParams({ account_id: selectedAccountId });
      if (bucketFilter !== "all") {
        params.append("bucket", bucketFilter);
      }
      const res = await fetch(`${API_BASE}/ads/?${params}`);
      if (!res.ok) throw new Error("Failed to fetch ads");
      return res.json();
    },
    enabled: !!selectedAccountId,
  });

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat("en-US").format(num);
  };

  const formatPercent = (num: number) => {
    // Metrics are already stored as percentages (e.g., 10.17 for 10.17%)
    return `${num.toFixed(2)}%`;
  };

  const formatCurrency = (micros: number) => {
    return `$${(micros / 1_000_000).toFixed(2)}`;
  };

  const getBucketBadge = (bucket: string) => {
    switch (bucket) {
      case "best":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-green-500/10 text-green-600 dark:text-green-400 text-xs font-mono font-bold">
            <TrendingUp className="h-3 w-3" />
            BEST
          </span>
        );
      case "worst":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-red-500/10 text-red-600 dark:text-red-400 text-xs font-mono font-bold">
            <TrendingDown className="h-3 w-3" />
            WORST
          </span>
        );
      default:
        return (
          <span className="px-2 py-1 rounded-md bg-muted text-muted-foreground text-xs font-mono">
            UNKNOWN
          </span>
        );
    }
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
          <h1 className="text-4xl font-display font-bold tracking-tight">Ad Performance</h1>
          <p className="mt-2 text-muted-foreground">
            Analyze and optimize your ad copy with AI-powered insights
          </p>
        </div>
      </motion.div>

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex flex-col gap-4 p-4 sm:p-6 rounded-lg border border-border/40 bg-card/30 backdrop-blur-sm w-full max-w-full"
      >
        <div className="w-full">
          <label className="text-xs sm:text-sm font-mono font-semibold text-muted-foreground mb-2 block">
            SELECT ACCOUNT
          </label>
          <Select value={selectedAccountId} onValueChange={setSelectedAccountId}>
            <SelectTrigger className="h-11 font-mono">
              <SelectValue placeholder="Choose an account..." />
            </SelectTrigger>
            <SelectContent>
              {accountsLoading ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  Loading accounts...
                </div>
              ) : accounts?.length === 0 ? (
                <div className="p-4 text-center">
                  <p className="text-sm text-muted-foreground mb-2">No accounts connected</p>
                  <Link href="/connect">
                    <Button size="sm" variant="outline">
                      Connect Account
                    </Button>
                  </Link>
                </div>
              ) : (
                accounts?.map((account) => (
                  <SelectItem key={account.id} value={String(account.id)} className="font-mono">
                    {account.customer_name} ({account.customer_id})
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>

        <div className="w-full">
          <label className="text-xs sm:text-sm font-mono font-semibold text-muted-foreground mb-2 block">
            FILTER BY PERFORMANCE
          </label>
          <div className="flex gap-2 w-full">
            {[
              { value: "all", label: "All" },
              { value: "best", label: "Best" },
              { value: "worst", label: "Worst" },
            ].map((filter) => (
              <Button
                key={filter.value}
                variant={bucketFilter === filter.value ? "default" : "outline"}
                size="sm"
                onClick={() => setBucketFilter(filter.value as typeof bucketFilter)}
                className="flex-1 font-mono text-xs sm:text-sm min-w-0"
                disabled={!selectedAccountId}
              >
                <Filter className="h-3 w-3 mr-1" />
                {filter.label}
              </Button>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Ads Table */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="border border-border/40 rounded-lg overflow-hidden bg-card/30 backdrop-blur-sm w-full max-w-full"
      >
        <div className="w-full overflow-x-auto">
          {/* Table Header - Hidden on mobile */}
          <div className="bg-muted/50 border-b border-border/40 px-4 sm:px-6 py-3 hidden md:block w-full min-w-[800px]">
            <div className="grid grid-cols-12 gap-2 sm:gap-4 text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              <div className="col-span-3">Ad Preview</div>
              <div className="col-span-1 text-right">Impr.</div>
              <div className="col-span-1 text-right">Clicks</div>
              <div className="col-span-1 text-right">CTR</div>
              <div className="col-span-1 text-right">Conv.</div>
              <div className="col-span-1 text-right">CVR</div>
              <div className="col-span-2 text-right">CPA</div>
              <div className="col-span-2 text-center">Status</div>
            </div>
          </div>

          {/* Table Body */}
          <div className="divide-y divide-border/40 w-full">
          {!selectedAccountId ? (
            <div className="p-12 text-center">
              <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
              <h3 className="text-lg font-display font-semibold mb-2">No Account Selected</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Select an account above to view ad performance data
              </p>
            </div>
          ) : adsLoading ? (
            <div className="p-12 text-center">
              <Loader2 className="h-8 w-8 text-primary animate-spin mx-auto mb-4" />
              <p className="text-sm text-muted-foreground font-mono">Loading ads...</p>
            </div>
          ) : adsError ? (
            <div className="p-12 text-center">
              <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
              <h3 className="text-lg font-display font-semibold mb-2">Error Loading Ads</h3>
              <p className="text-sm text-muted-foreground">{(adsError as Error).message}</p>
            </div>
          ) : ads?.length === 0 ? (
            <div className="p-12 text-center">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
                <Filter className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-display font-semibold mb-2">No Ads Found</h3>
              <p className="text-sm text-muted-foreground">
                {bucketFilter === "all"
                  ? "This account has no ads yet"
                  : `No ${bucketFilter} performing ads found`}
              </p>
            </div>
          ) : (
            <div className="hidden md:block min-w-[800px]">
            {ads?.map((ad, i) => (
              <motion.div
                key={ad.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Link href={`/ads/${ad.id}`}>
                  {/* Desktop Table Row */}
                  <div className="grid grid-cols-12 gap-2 sm:gap-4 px-4 sm:px-6 py-4 hover:bg-muted/30 transition-colors group cursor-pointer">
                    {/* Ad Preview */}
                    <div className="col-span-3 space-y-1">
                      <div className="text-sm font-semibold line-clamp-1 group-hover:text-primary transition-colors">
                        {ad.headlines?.[0] || "No headline"}
                      </div>
                      <div className="text-xs text-muted-foreground line-clamp-2">
                        {ad.descriptions?.[0] || "No description"}
                      </div>
                      <div className="text-xs font-mono text-muted-foreground">
                        ID: {ad.ad_id}
                      </div>
                    </div>

                    {/* Metrics */}
                    <div className="col-span-1 text-right font-mono text-sm">
                      {formatNumber(ad.metrics_90d?.impressions || 0)}
                    </div>
                    <div className="col-span-1 text-right font-mono text-sm">
                      {formatNumber(ad.metrics_90d?.clicks || 0)}
                    </div>
                    <div className="col-span-1 text-right font-mono text-sm font-semibold text-primary">
                      {formatPercent(ad.metrics_90d?.ctr || 0)}
                    </div>
                    <div className="col-span-1 text-right font-mono text-sm">
                      {formatNumber(ad.metrics_90d?.conversions || 0)}
                    </div>
                    <div className="col-span-1 text-right font-mono text-sm font-semibold text-primary">
                      {formatPercent(ad.metrics_90d?.cvr || 0)}
                    </div>
                    <div className="col-span-2 text-right font-mono text-sm">
                      {ad.metrics_90d?.cost_per_conversion_micros
                        ? formatCurrency(ad.metrics_90d.cost_per_conversion_micros)
                        : "—"}
                    </div>

                    {/* Bucket Badge */}
                    <div className="col-span-2 flex items-center justify-center gap-2">
                      {getBucketBadge(ad.bucket)}
                      <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                    </div>
                  </div>
                </Link>
              </motion.div>
            ))}
            </div>
          )}
          {/* Mobile Card Views */}
          {ads && ads.length > 0 && (
            <div className="md:hidden">
            {ads.map((ad, i) => (
              <motion.div
                key={ad.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Link href={`/ads/${ad.id}`}>
                  <div className="p-4 hover:bg-muted/30 transition-colors group cursor-pointer">
                    <div className="space-y-3">
                      {/* Header */}
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 space-y-1 min-w-0">
                          <div className="text-sm font-semibold line-clamp-2 group-hover:text-primary transition-colors">
                            {ad.headlines?.[0] || "No headline"}
                          </div>
                          <div className="text-xs text-muted-foreground line-clamp-2">
                            {ad.descriptions?.[0] || "No description"}
                          </div>
                        </div>
                        <div className="flex-shrink-0">{getBucketBadge(ad.bucket)}</div>
                      </div>

                      {/* Key Metrics */}
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div>
                          <div className="text-muted-foreground mb-0.5">CTR</div>
                          <div className="font-mono font-semibold text-primary">
                            {formatPercent(ad.metrics_90d?.ctr || 0)}
                          </div>
                        </div>
                        <div>
                          <div className="text-muted-foreground mb-0.5">CVR</div>
                          <div className="font-mono font-semibold text-primary">
                            {formatPercent(ad.metrics_90d?.cvr || 0)}
                          </div>
                        </div>
                        <div>
                          <div className="text-muted-foreground mb-0.5">Clicks</div>
                          <div className="font-mono">{formatNumber(ad.metrics_90d?.clicks || 0)}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground mb-0.5">Conv.</div>
                          <div className="font-mono">{formatNumber(ad.metrics_90d?.conversions || 0)}</div>
                        </div>
                      </div>

                      {/* Footer */}
                      <div className="flex items-center justify-between text-xs">
                        <div className="font-mono text-muted-foreground truncate">ID: {ad.ad_id}</div>
                        <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all flex-shrink-0" />
                      </div>
                    </div>
                  </div>
                </Link>
              </motion.div>
            ))}
            </div>
          )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
