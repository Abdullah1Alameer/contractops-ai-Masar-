"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Known Bug 3: /negotiations and /negotiations/monitor were two confusing,
// overlapping destinations (the monitor's email-thread feature had no
// seeded data for the real negotiation flow and read as broken/empty).
// Unified into one /negotiations page. This route is kept, redirecting,
// so any old link/bookmark still lands somewhere useful instead of 404ing.
export default function NegotiationMonitorRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/negotiations");
  }, [router]);
  return null;
}
