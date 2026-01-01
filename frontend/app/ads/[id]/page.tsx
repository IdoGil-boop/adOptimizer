"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  Loader2,
  Sparkles,
  TrendingDown,
  TrendingUp,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useToast } from "@/components/ui/use-toast";

type Ad = {
  id: number;
  ad_id: string;
  ad_type: string;
  headlines: string[];
  descriptions: string[];
  final_urls: string[];
  bucket: "best" | "worst" | "unknown";
  status: string;
  campaign_name: string;
  ad_group_name: string;
  google_ads_created_at: string | null;
  metrics_90d: {
    impressions: number;
    clicks: number;
    ctr: number | null;
    conversions: number;
    cvr: number | null;
    cost_micros: number;
    cost_per_conversion_micros: number | null;
    average_cpc_micros: number;
  };
  headline_performance?: {
    headlines: Array<{
      text: string;
      impressions: number;
      clicks: number;
      conversions: number;
      cost_micros: number;
      ctr: number | null;
    }>;
    descriptions: Array<{
      text: string;
      impressions: number;
      clicks: number;
      conversions: number;
      cost_micros: number;
      ctr: number | null;
    }>;
  };
  keyword_quality_scores?: Array<{
    criterion_id: string;
    text: string;
    match_type: string | null;
    status: string | null;
    quality_score: number | null;
    creative_quality_score: string | null;
    post_click_quality_score: string | null;
    search_predicted_ctr: string | null;
  }>;
};

type Suggestion = {
  id: number;
  headlines: string[];
  descriptions: string[];
  exemplar_ad_ids: string[];
  validation_passed: boolean;
  validation_errors: string[] | null;
  created_at: string;
};

const API_BASE = "http://localhost:8000";

export default function AdDetailPage() {
  const params = useParams();
  const adId = params.id as string;
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [showAllHeadlines, setShowAllHeadlines] = useState(false);
  const [showAllDescriptions, setShowAllDescriptions] = useState(false);

  // Fetch ad details
  const {
    data: ad,
    isLoading: adLoading,
    error: adError,
  } = useQuery<Ad>({
    queryKey: ["ad", adId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/ads/${adId}`);
      if (!res.ok) throw new Error("Failed to fetch ad");
      return res.json();
    },
  });

  // Fetch suggestions
  const {
    data: suggestions,
    isLoading: suggestionsLoading,
    refetch: refetchSuggestions,
  } = useQuery<Suggestion[]>({
    queryKey: ["suggestions", adId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/suggestions/${adId}`);
      if (!res.ok) {
        if (res.status === 404) return [];
        throw new Error("Failed to fetch suggestions");
      }
      return res.json();
    },
  });

  // Generate suggestions mutation
  const generateMutation = useMutation({
    mutationFn: async () => {
      console.log("Generating suggestions for ad:", adId);
      const res = await fetch(`${API_BASE}/suggestions/${adId}/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      console.log("Response status:", res.status);
      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: "Unknown error" }));
        console.error("Generation error:", error);
        throw new Error(error.detail || "Failed to generate suggestions");
      }
      const data = await res.json();
      console.log("Generation success:", data);
      return data;
    },
    onSuccess: () => {
      toast({
        title: "Suggestions Generated",
        description: "AI-powered ad copy variants have been created successfully",
      });
      refetchSuggestions();
    },
    onError: (error: Error) => {
      console.error("Mutation error:", error);
      const errorMessage = error.message;
      toast({
        title: "Generation Failed",
        description: errorMessage.includes("No high-performing ads")
          ? "Please run scoring first to classify ads. Go to Accounts page and click 'Score Ads'."
          : errorMessage,
        variant: "destructive",
      });
    },
  });

  const formatNumber = (num: number | null | undefined) => {
    if (num == null) return "—";
    return new Intl.NumberFormat("en-US").format(num);
  };

  const formatPercent = (num: number | null | undefined) => {
    // Metrics are already stored as percentages (e.g., 10.17 for 10.17%)
    if (num == null) return "—";
    return `${num.toFixed(2)}%`;
  };

  const formatCurrency = (micros: number | null | undefined) => {
    if (micros == null) return "—";
    return `$${(micros / 1_000_000).toFixed(2)}`;
  };

  const getBucketColor = (bucket: string) => {
    switch (bucket) {
      case "best":
        return "text-green-600 dark:text-green-400";
      case "worst":
        return "text-red-600 dark:text-red-400";
      default:
        return "text-muted-foreground";
    }
  };

  const getBucketIcon = (bucket: string) => {
    switch (bucket) {
      case "best":
        return <TrendingUp className="h-5 w-5" />;
      case "worst":
        return <TrendingDown className="h-5 w-5" />;
      default:
        return <AlertCircle className="h-5 w-5" />;
    }
  };

  if (adLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <Loader2 className="h-12 w-12 text-primary animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground font-mono">Loading ad details...</p>
        </div>
      </div>
    );
  }

  if (adError || !ad) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-display font-semibold mb-2">Failed to Load Ad</h3>
          <p className="text-sm text-muted-foreground mb-4">
            {(adError as Error)?.message || "Ad not found"}
          </p>
          <Link href="/ads">
            <Button variant="outline">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Ads
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const headlinesToShow = showAllHeadlines ? ad.headlines : ad.headlines.slice(0, 3);
  const descriptionsToShow = showAllDescriptions ? ad.descriptions : ad.descriptions.slice(0, 2);

  return (
    <div className="space-y-8 w-full max-w-full overflow-x-hidden">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row items-start justify-between gap-4 w-full"
      >
        <div className="space-y-2">
          <Link href="/ads">
            <Button variant="ghost" size="sm" className="mb-2 -ml-2">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Ads
            </Button>
          </Link>
          <div className="flex items-center gap-3">
            <div className={`${getBucketColor(ad.bucket)}`}>{getBucketIcon(ad.bucket)}</div>
            <h1 className="text-4xl font-display font-bold tracking-tight">Ad Details</h1>
          </div>
          <p className="text-muted-foreground font-mono">ID: {ad.ad_id}</p>
        </div>

        <Button
          size="lg"
          onClick={(e) => {
            e.preventDefault();
            console.log("Button clicked, adId:", adId);
            generateMutation.mutate();
          }}
          disabled={generateMutation.isPending || !adId}
          className="shadow-lg shadow-primary/20 w-full sm:w-auto"
        >
          {generateMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4 mr-2" />
              Generate Suggestions
            </>
          )}
        </Button>
      </motion.div>

      <div className="grid lg:grid-cols-3 gap-8 w-full max-w-full">
        {/* Left Column: Ad Content */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="lg:col-span-2 space-y-6"
        >
          {/* Ad Copy */}
          <div className="border border-border/40 rounded-lg p-6 bg-card/30 backdrop-blur-sm space-y-6">
            <div>
              <h3 className="text-sm font-mono font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Headlines ({ad.headlines.length})
              </h3>
              <div className="space-y-2">
                {headlinesToShow.map((headline, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 + i * 0.05 }}
                    className="flex items-start gap-3 p-3 rounded-md bg-muted/30"
                  >
                    <span className="font-mono text-xs font-bold text-primary mt-0.5">
                      H{i + 1}
                    </span>
                    <span className="text-sm flex-1">{headline}</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      {headline.length}/30
                    </span>
                  </motion.div>
                ))}
              </div>
              {ad.headlines.length > 3 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2 w-full"
                  onClick={() => setShowAllHeadlines(!showAllHeadlines)}
                >
                  {showAllHeadlines ? (
                    <>
                      <ChevronUp className="h-4 w-4 mr-2" />
                      Show Less
                    </>
                  ) : (
                    <>
                      <ChevronDown className="h-4 w-4 mr-2" />
                      Show All {ad.headlines.length} Headlines
                    </>
                  )}
                </Button>
              )}
            </div>

            <div>
              <h3 className="text-sm font-mono font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Descriptions ({ad.descriptions.length})
              </h3>
              <div className="space-y-2">
                {descriptionsToShow.map((description, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.4 + i * 0.05 }}
                    className="flex items-start gap-3 p-3 rounded-md bg-muted/30"
                  >
                    <span className="font-mono text-xs font-bold text-primary mt-0.5">
                      D{i + 1}
                    </span>
                    <span className="text-sm flex-1">{description}</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      {description.length}/90
                    </span>
                  </motion.div>
                ))}
              </div>
              {ad.descriptions.length > 2 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2 w-full"
                  onClick={() => setShowAllDescriptions(!showAllDescriptions)}
                >
                  {showAllDescriptions ? (
                    <>
                      <ChevronUp className="h-4 w-4 mr-2" />
                      Show Less
                    </>
                  ) : (
                    <>
                      <ChevronDown className="h-4 w-4 mr-2" />
                      Show All {ad.descriptions.length} Descriptions
                    </>
                  )}
                </Button>
              )}
            </div>
          </div>

          {/* Suggestions */}
          <div className="border border-border/40 rounded-lg p-6 bg-card/30 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5 text-primary" />
                <h3 className="text-lg font-display font-semibold">AI Suggestions</h3>
              </div>
              {suggestions && suggestions.length > 0 && (
                <span className="text-sm font-mono text-muted-foreground">
                  {suggestions.length} variant{suggestions.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>

            {suggestionsLoading ? (
              <div className="py-12 text-center">
                <Loader2 className="h-8 w-8 text-primary animate-spin mx-auto mb-4" />
                <p className="text-sm text-muted-foreground font-mono">Loading suggestions...</p>
              </div>
            ) : !suggestions || suggestions.length === 0 ? (
              <div className="py-12 text-center">
                <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="h-8 w-8 text-muted-foreground" />
                </div>
                <h4 className="text-lg font-display font-semibold mb-2">No Suggestions Yet</h4>
                <p className="text-sm text-muted-foreground mb-4">
                  Click "Generate Suggestions" to create AI-powered ad copy variants
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {suggestions.map((suggestion, i) => (
                  <motion.div
                    key={suggestion.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="border border-border/40 rounded-lg p-5 bg-card/50 space-y-4"
                  >
                    {/* Validation Status */}
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-semibold text-muted-foreground">
                        VARIANT #{i + 1}
                      </span>
                      {suggestion.validation_passed ? (
                        <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                          <CheckCircle2 className="h-4 w-4" />
                          <span className="text-xs font-mono font-semibold">VALIDATED</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
                          <XCircle className="h-4 w-4" />
                          <span className="text-xs font-mono font-semibold">INVALID</span>
                        </div>
                      )}
                    </div>

                    {/* Headlines */}
                    <div>
                      <h5 className="text-xs font-mono font-semibold uppercase text-muted-foreground mb-2">
                        Headlines
                      </h5>
                      <div className="space-y-1">
                        {suggestion.headlines.map((headline, j) => (
                          <div key={j} className="text-sm flex items-start gap-2">
                            <span className="font-mono text-xs text-primary">H{j + 1}</span>
                            <span className="flex-1">{headline}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Descriptions */}
                    <div>
                      <h5 className="text-xs font-mono font-semibold uppercase text-muted-foreground mb-2">
                        Descriptions
                      </h5>
                      <div className="space-y-1">
                        {suggestion.descriptions.map((description, j) => (
                          <div key={j} className="text-sm flex items-start gap-2">
                            <span className="font-mono text-xs text-primary">D{j + 1}</span>
                            <span className="flex-1">{description}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Exemplars */}
                    {suggestion.exemplar_ad_ids && suggestion.exemplar_ad_ids.length > 0 && (
                      <div className="pt-3 border-t border-border/40">
                        <p className="text-xs text-muted-foreground">
                          Based on top performers:{" "}
                          <span className="font-mono">
                            {suggestion.exemplar_ad_ids.join(", ")}
                          </span>
                        </p>
                      </div>
                    )}

                    {/* Validation Errors */}
                    {suggestion.validation_errors && suggestion.validation_errors.length > 0 && (
                      <div className="pt-3 border-t border-border/40">
                        <p className="text-xs text-red-600 dark:text-red-400 font-mono">
                          ⚠ {suggestion.validation_errors.join(", ")}
                        </p>
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </motion.div>

        {/* Right Column: Metrics */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="space-y-6"
        >
          {/* Campaign Info */}
          <div className="border border-border/40 rounded-lg p-6 bg-card/30 backdrop-blur-sm space-y-4">
            <h3 className="text-sm font-mono font-semibold uppercase tracking-wider text-muted-foreground">
              Campaign Info
            </h3>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Campaign</p>
                <p className="text-sm font-semibold">{ad.campaign_name}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Ad Group</p>
                <p className="text-sm font-semibold">{ad.ad_group_name}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Status</p>
                <p className="text-sm font-mono font-semibold uppercase">{ad.status}</p>
              </div>
              {ad.google_ads_created_at && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Created</p>
                  <p className="text-sm font-mono">
                    {new Date(ad.google_ads_created_at).toLocaleDateString()}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Performance Metrics */}
          <div className="border border-border/40 rounded-lg p-6 bg-card/30 backdrop-blur-sm space-y-4">
            <h3 className="text-sm font-mono font-semibold uppercase tracking-wider text-muted-foreground">
              90-Day Performance
            </h3>
            <div className="space-y-4">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Impressions</p>
                <p className="text-2xl font-mono font-bold">
                  {formatNumber(ad.metrics_90d.impressions)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Clicks</p>
                <p className="text-2xl font-mono font-bold">
                  {formatNumber(ad.metrics_90d.clicks)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Click-Through Rate</p>
                <p className="text-2xl font-mono font-bold text-primary">
                  {formatPercent(ad.metrics_90d.ctr)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Conversions</p>
                <p className="text-2xl font-mono font-bold">
                  {formatNumber(ad.metrics_90d.conversions)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Conversion Rate</p>
                <p className="text-2xl font-mono font-bold text-primary">
                  {formatPercent(ad.metrics_90d.cvr)}
                </p>
              </div>
              <div className="pt-4 border-t border-border/40">
                <p className="text-xs text-muted-foreground mb-1">Total Spend</p>
                <p className="text-2xl font-mono font-bold">
                  {formatCurrency(ad.metrics_90d.cost_micros)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Avg. CPC</p>
                <p className="text-2xl font-mono font-bold">
                  {formatCurrency(ad.metrics_90d.average_cpc_micros)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Cost Per Conversion</p>
                <p className="text-2xl font-mono font-bold">
                  {ad.metrics_90d.cost_per_conversion_micros
                    ? formatCurrency(ad.metrics_90d.cost_per_conversion_micros)
                    : "—"}
                </p>
              </div>
            </div>
          </div>

          {/* Headline Performance */}
          {ad.headline_performance && (
            <div className="border border-border/40 rounded-lg p-6 bg-card/30 backdrop-blur-sm space-y-4">
              <h3 className="text-sm font-mono font-semibold uppercase tracking-wider text-muted-foreground">
                Headline Performance (90d)
              </h3>
              {ad.headline_performance.headlines && ad.headline_performance.headlines.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-mono font-semibold text-muted-foreground">Headlines</h4>
                  <div className="space-y-2">
                    {ad.headline_performance.headlines.map((perf, i) => (
                      <div key={i} className="p-3 rounded-md bg-muted/30 space-y-1">
                        <p className="text-sm font-semibold">{perf.text}</p>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-muted-foreground">Impressions: </span>
                            <span className="font-mono">{formatNumber(perf.impressions ?? 0)}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Clicks: </span>
                            <span className="font-mono">{formatNumber(perf.clicks ?? 0)}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">CTR: </span>
                            <span className="font-mono">{formatPercent(perf.ctr ?? null)}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Conversions: </span>
                            <span className="font-mono">{formatNumber(perf.conversions ?? 0)}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {ad.headline_performance.descriptions && ad.headline_performance.descriptions.length > 0 && (
                <div className="space-y-3 pt-4 border-t border-border/40">
                  <h4 className="text-xs font-mono font-semibold text-muted-foreground">Descriptions</h4>
                  <div className="space-y-2">
                    {ad.headline_performance.descriptions.map((perf, i) => (
                      <div key={i} className="p-3 rounded-md bg-muted/30 space-y-1">
                        <p className="text-sm font-semibold">{perf.text}</p>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-muted-foreground">Impressions: </span>
                            <span className="font-mono">{formatNumber(perf.impressions ?? 0)}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Clicks: </span>
                            <span className="font-mono">{formatNumber(perf.clicks ?? 0)}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">CTR: </span>
                            <span className="font-mono">{formatPercent(perf.ctr ?? null)}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Conversions: </span>
                            <span className="font-mono">{formatNumber(perf.conversions ?? 0)}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Keyword Quality Scores */}
          {ad.keyword_quality_scores && ad.keyword_quality_scores.length > 0 && (
            <div className="border border-border/40 rounded-lg p-6 bg-card/30 backdrop-blur-sm space-y-4">
              <h3 className="text-sm font-mono font-semibold uppercase tracking-wider text-muted-foreground">
                Keyword Quality Scores
              </h3>
              <div className="space-y-2">
                {ad.keyword_quality_scores.map((kw, i) => (
                  <div key={i} className="p-3 rounded-md bg-muted/30 space-y-1">
                    <p className="text-sm font-semibold">{kw.text}</p>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {kw.quality_score !== null && (
                        <div>
                          <span className="text-muted-foreground">Quality Score: </span>
                          <span className="font-mono font-semibold">{kw.quality_score}/10</span>
                        </div>
                      )}
                      {kw.creative_quality_score && (
                        <div>
                          <span className="text-muted-foreground">Ad Relevance: </span>
                          <span className="font-mono">{kw.creative_quality_score}</span>
                        </div>
                      )}
                      {kw.post_click_quality_score && (
                        <div>
                          <span className="text-muted-foreground">Landing Page: </span>
                          <span className="font-mono">{kw.post_click_quality_score}</span>
                        </div>
                      )}
                      {kw.search_predicted_ctr && (
                        <div>
                          <span className="text-muted-foreground">Expected CTR: </span>
                          <span className="font-mono">{kw.search_predicted_ctr}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
