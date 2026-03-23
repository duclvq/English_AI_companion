"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import QuestionCard from "@/components/QuestionCard";
import ExplanationPanel from "@/components/ExplanationPanel";
import StatsBar from "@/components/StatsBar";

interface Question {
  id: string;
  type: string;
  difficulty: number;
  topic: string;
  question_text: string;
  choices: string[];
}

export default function FeedPage() {
  const router = useRouter();
  const [question, setQuestion] = useState<Question | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [streak, setStreak] = useState(0);
  const [total, setTotal] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [explainId, setExplainId] = useState<string | null>(null);
  const [showExplain, setShowExplain] = useState(false);
  const [key, setKey] = useState(0); // force re-mount of QuestionCard

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    loadStats();
    loadNext();
  }, []);

  async function loadStats() {
    const res = await apiFetch("/progress/stats");
    if (res.ok) {
      const s = await res.json();
      setStreak(s.streak);
      setTotal(s.total_answered);
      setCorrect(s.correct_count);
    }
  }

  async function loadNext() {
    setLoading(true);
    setError("");
    const res = await apiFetch("/questions/next");
    if (res.status === 403) {
      router.replace("/onboarding");
      return;
    }
    if (res.ok) {
      setQuestion(await res.json());
    } else {
      setError("No more questions available. Check back later!");
    }
    setLoading(false);
  }

  const handleAnswered = useCallback((qId: string, chosen: number, isCorrect: boolean, correctIdx: number, newStreak: number) => {
    setStreak(newStreak);
    setTotal((t) => t + 1);
    if (isCorrect) {
      setCorrect((c) => c + 1);
      // auto-advance after 1.5s
      setTimeout(() => {
        setKey((k) => k + 1);
        loadNext();
      }, 1500);
    } else {
      // show explanation
      setExplainId(qId);
      setTimeout(() => setShowExplain(true), 800);
    }
  }, []);

  function closeExplanation() {
    setShowExplain(false);
    setExplainId(null);
    setKey((k) => k + 1);
    loadNext();
  }

  if (loading && !question) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-pulse text-brand text-lg">Loading question...</div>
    </div>
  );

  return (
    <div className="min-h-screen">
      <StatsBar streak={streak} total={total} correct={correct} />
      <div className="pt-12">
        {error ? (
          <div className="flex flex-col items-center justify-center min-h-[80vh] p-4 text-center">
            <p className="text-slate-500 mb-4">{error}</p>
            <button onClick={loadNext} className="bg-brand text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-green-700 transition">
              Try again
            </button>
          </div>
        ) : question ? (
          <QuestionCard key={key} question={question} onAnswered={handleAnswered} />
        ) : null}
      </div>
      <ExplanationPanel questionId={explainId || ""} visible={showExplain} onClose={closeExplanation} />
    </div>
  );
}
