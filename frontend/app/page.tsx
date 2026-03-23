"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(isLoggedIn() ? "/feed" : "/login");
  }, [router]);
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-pulse text-brand text-xl font-semibold">Loading...</div>
    </div>
  );
}
