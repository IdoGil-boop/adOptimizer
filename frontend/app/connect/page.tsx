"use client";

import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Database, Lock, Sparkles, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function ConnectPage() {
  const router = useRouter();
  const [isConnecting, setIsConnecting] = useState(false);

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      // Fetch authorization URL from backend
      const response = await fetch("http://localhost:8000/oauth/google-ads/start");
      const data = await response.json();
      
      // Redirect to Google OAuth consent screen
      window.location.href = data.authorization_url;
    } catch (error) {
      console.error("Failed to initiate OAuth:", error);
      setIsConnecting(false);
    }
  };

  const benefits = [
    {
      icon: Database,
      title: "90-Day Performance Data",
      description: "Comprehensive metrics including CTR, CVR, CPA, and conversion tracking",
    },
    {
      icon: Sparkles,
      title: "AI-Powered Analysis",
      description: "Identify your best and worst performing ads automatically",
    },
    {
      icon: Zap,
      title: "Smart Suggestions",
      description: "Generate optimized ad copy based on your top performers",
    },
  ];

  const permissions = [
    "Read campaign and ad group data",
    "View ad performance metrics",
    "Access conversion tracking data",
  ];

  return (
    <div className="space-y-12 w-full max-w-full overflow-x-hidden">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center space-y-4 w-full px-2"
      >
        <h1 className="text-3xl sm:text-4xl lg:text-5xl font-display font-bold tracking-tight px-2">
          Connect Your Google Ads Account
        </h1>
        <p className="text-base sm:text-lg lg:text-xl text-muted-foreground max-w-2xl mx-auto px-2">
          Unlock AI-powered ad copy optimization by connecting your account in seconds
        </p>
      </motion.div>

      <div className="grid lg:grid-cols-2 gap-6 sm:gap-8 lg:gap-12 max-w-6xl mx-auto w-full px-2 sm:px-4">
        {/* Left Column: CTA */}
        <motion.div
          initial={{ opacity: 0, x: -40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="space-y-6 sm:space-y-8 w-full min-w-0"
        >
          {/* Main CTA Card */}
          <div className="border-2 border-primary/20 rounded-lg p-4 sm:p-6 lg:p-8 bg-card/50 backdrop-blur-sm space-y-4 sm:space-y-6 w-full max-w-full overflow-hidden">
            <div className="space-y-4 w-full">
              <div className="flex items-center gap-3 min-w-0">
                <div className="h-10 w-10 sm:h-12 sm:w-12 rounded-md bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Lock className="h-5 w-5 sm:h-6 sm:w-6 text-primary" />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="text-base sm:text-lg font-display font-semibold">Secure Connection</h3>
                  <p className="text-xs sm:text-sm text-muted-foreground font-mono">OAuth 2.0 Protocol</p>
                </div>
              </div>

              <p className="text-sm sm:text-base text-muted-foreground break-words">
                We use Google's secure OAuth authentication. We never see your password and can
                only access data you explicitly authorize.
              </p>
            </div>

            <Button
              size="lg"
              className="w-full min-h-[48px] sm:min-h-[56px] h-auto py-3 sm:py-4 px-4 sm:px-8 text-xs sm:text-sm lg:text-lg font-display shadow-lg shadow-primary/20 !whitespace-normal break-words"
              onClick={handleConnect}
              disabled={isConnecting}
            >
              <span className="flex items-center justify-center gap-2 flex-wrap px-2">
                {isConnecting ? (
                  <>
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      className="flex-shrink-0"
                    >
                      <Zap className="h-4 w-4 sm:h-5 sm:w-5" />
                    </motion.div>
                    <span className="text-center">Connecting...</span>
                  </>
                ) : (
                  <>
                    <span className="text-center whitespace-normal break-words">Connect Google Ads Account</span>
                    <ArrowRight className="h-4 w-4 sm:h-5 sm:w-5 flex-shrink-0" />
                  </>
                )}
              </span>
            </Button>

            <p className="text-xs text-center text-muted-foreground font-mono break-words px-2">
              By connecting, you agree to grant read-only access to your ad performance data
            </p>
          </div>

          {/* Permissions */}
          <div className="space-y-4 w-full">
            <h3 className="text-xs sm:text-sm font-display font-semibold uppercase tracking-wider text-muted-foreground">
              Required Permissions
            </h3>
            <div className="space-y-2 w-full">
              {permissions.map((permission, i) => (
                <motion.div
                  key={permission}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4, delay: 0.4 + i * 0.1 }}
                  className="flex items-start gap-2 sm:gap-3 p-2 sm:p-3 rounded-md bg-muted/30 w-full min-w-0"
                >
                  <CheckCircle2 className="h-4 w-4 sm:h-5 sm:w-5 text-primary flex-shrink-0 mt-0.5" />
                  <span className="text-xs sm:text-sm font-mono break-words min-w-0 flex-1">{permission}</span>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Right Column: Benefits */}
        <motion.div
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="space-y-4 sm:space-y-6 w-full min-w-0"
        >
          <h3 className="text-xl sm:text-2xl font-display font-bold">What You'll Get</h3>

          <div className="space-y-4 w-full">
            {benefits.map((benefit, i) => {
              const Icon = benefit.icon;
              return (
                <motion.div
                  key={benefit.title}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.5 + i * 0.15 }}
                  className="relative border border-border/40 rounded-lg p-4 sm:p-6 bg-card/30 backdrop-blur-sm w-full overflow-hidden cursor-default"
                >
                  <div className="flex gap-3 sm:gap-4 min-w-0">
                    <div className="h-10 w-10 sm:h-12 sm:w-12 rounded-md bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <Icon className="h-5 w-5 sm:h-6 sm:w-6 text-primary" />
                    </div>
                    <div className="space-y-2 min-w-0 flex-1">
                      <h4 className="text-base sm:text-lg font-display font-semibold break-words">{benefit.title}</h4>
                      <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed break-words">
                        {benefit.description}
                      </p>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>

          {/* How it works */}
          <div className="border-t border-border/40 pt-4 sm:pt-6 mt-6 sm:mt-8 w-full">
            <h4 className="text-xs sm:text-sm font-display font-semibold uppercase tracking-wider text-muted-foreground mb-3 sm:mb-4">
              How It Works
            </h4>
            <ol className="space-y-2 sm:space-y-3 w-full">
              {[
                "Click the connect button above",
                "Sign in with your Google account",
                "Grant read-only permissions",
                "We sync your ad data automatically",
                "Start optimizing your ad copy with AI",
              ].map((step, i) => (
                <motion.li
                  key={i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.3, delay: 0.8 + i * 0.1 }}
                  className="flex items-baseline gap-2 sm:gap-3 text-xs sm:text-sm min-w-0"
                >
                  <span className="font-mono font-bold text-primary flex-shrink-0">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="text-muted-foreground break-words flex-1">{step}</span>
                </motion.li>
              ))}
            </ol>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
