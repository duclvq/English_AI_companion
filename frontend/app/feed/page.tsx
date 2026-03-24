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

interface CourseComplete {
  course_complete: true;
  total_answered: number;
  correct_count: number;
  accuracy: number;
  weak_topics: Record<string, number>;
  strong_topics: Record<string, number>;
  streak: number;
  xp_total: number;
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
  const [key, setKey] = useState(0);
  const [courseComplete, setCourseComplete] = useState<CourseComplete | null>(null);
  const [generating, setGenerating] = useState(false);

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
    setCourseComplete(null);
    const res = await apiFetch("/questions/next");
    if (res.status === 403) {
      router.replace("/onboarding");
      return;
    }
    if (res.ok) {
      const data = await res.json();
      if (data.course_complete) {
        setCourseComplete(data);
        setQuestion(null);
      } else {
        setQuestion(data);
      }
    } else {
      setError("Something went wrong. Try again!");
    }
    setLoading(false);
  }

  const handleAnswered = useCallback((qId: string, chosen: number, isCorrect: boolean, correctIdx: number, newStreak: number) => {
    setStreak(newStreak);
    setTotal((t) => t + 1);
    if (isCorrect) {
      setCorrect((c) => c + 1);
      setTimeout(() => { setKey((k) => k + 1); loadNext(); }, 1500);
    } else {
      setExplainId(qId);
      setTimeout(() => setShowExplain(true), 800);
    }
  }, []);

  const handleSkipped = useCallback((qId: string, correctIdx: number) => {
    setTotal((t) => t + 1);
    // Show explanation for skipped questions too
    setExplainId(qId);
    setTimeout(() => setShowExplain(true), 1200);
  }, []);

  function closeExplanation() {
    setShowExplain(false);
    setExplainId(null);
    setKey((k) => k + 1);
    loadNext();
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      const res = await apiFetch("/questions/generate", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        if (data.generated > 0) {
          setCourseComplete(null);
          loadNext();
        } else {
          setError("Could not generate questions. Try again later.");
        }
      }
    } catch {
      setError("Failed to generate questions.");
    } finally {
      setGenerating(false);
    }
  }

  if (loading && !question && !courseComplete) return (
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
            <button onClick={() => { setError(""); loadNext(); }} className="bg-brand text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-green-700 transition">
              Try again
            </button>
          </div>
        ) : courseComplete ? (
          <CourseCompleteScreen data={courseComplete} onGenerate={handleGenerate} generating={generating} />
        ) : question ? (
          <QuestionCard key={key} question={question} onAnswered={handleAnswered} onSkipped={handleSkipped} />
        ) : null}
      </div>
      <ExplanationPanel questionId={explainId || ""} visible={showExplain} onClose={closeExplanation} />
    </div>
  );
}

const GEN_STEPS = [
  "Analyzing your performance...",
  "Identifying weak areas...",
  "Crafting personalized questions...",
  "Almost there...",
];

function CourseCompleteScreen({ data, onGenerate, generating }: {
  data: CourseComplete;
  onGenerate: () => void;
  generating: boolean;
}) {
  const [stepIdx, setStepIdx] = useState(0);
  const weakEntries = Object.entries(data.weak_topics).sort((a, b) => a[1] - b[1]);
  const strongEntries = Object.entries(data.strong_topics).sort((a, b) => b[1] - a[1]);

  useEffect(() => {
    if (!generating) { setStepIdx(0); return; }
    const timer = setInterval(() => {
      setStepIdx((i) => (i < GEN_STEPS.length - 1 ? i + 1 : i));
    }, 3000);
    return () => clearInterval(timer);
  }, [generating]);

  if (generating) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[85vh] p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-lg w-full mx-auto text-center">
          <div className="text-5xl mb-4 animate-bounce">🧠</div>
          <h2 className="text-lg font-bold text-slate-800 mb-2">Generating Questions</h2>
          <p className="text-sm text-slate-500 mb-6">{GEN_STEPS[stepIdx]}</p>
          <div className="w-full bg-slate-100 rounded-full h-2 mb-4 overflow-hidden">
            <div
              className="bg-brand h-2 rounded-full transition-all duration-1000 ease-out"
              style={{ width: `${Math.min(((stepIdx + 1) / GEN_STEPS.length) * 100, 95)}%` }}
            />
          </div>
          <div className="flex justify-center gap-1.5">
            {GEN_STEPS.map((_, i) => (
              <div key={i} className={`w-2 h-2 rounded-full transition-colors ${i <= stepIdx ? "bg-brand" : "bg-slate-200"}`} />
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-4">AI is creating 20 questions focused on your weak areas</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[85vh] p-4">
      <div className="bg-white rounded-2xl shadow-lg p-6 max-w-lg w-full mx-auto text-center">
        <div className="text-4xl mb-3">🎉</div>
        <h2 className="text-xl font-bold text-slate-800 mb-1">Course Complete!</h2>
        <p className="text-sm text-slate-500 mb-6">You&apos;ve answered all available questions. Here&apos;s your performance:</p>

        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="bg-green-50 rounded-xl p-3">
            <div className="text-2xl font-bold text-green-600">{data.accuracy}%</div>
            <div className="text-xs text-slate-500">Accuracy</div>
          </div>
          <div className="bg-blue-50 rounded-xl p-3">
            <div className="text-2xl font-bold text-blue-600">{data.xp_total}</div>
            <div className="text-xs text-slate-500">Total XP</div>
          </div>
          <div className="bg-amber-50 rounded-xl p-3">
            <div className="text-2xl font-bold text-amber-600">🔥 {data.streak}</div>
            <div className="text-xs text-slate-500">Streak</div>
          </div>
        </div>

        <div className="text-left mb-6">
          <div className="text-sm font-medium text-slate-600 mb-1">
            {data.total_answered} questions answered · {data.correct_count} correct
          </div>

          {weakEntries.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-1.5">Needs practice</div>
              <div className="flex flex-wrap gap-1.5">
                {weakEntries.map(([topic, score]) => (
                  <span key={topic} className="text-xs bg-red-50 text-red-600 px-2.5 py-1 rounded-full">
                    {topic.replace(/_/g, " ")} · {Math.round(score * 100)}%
                  </span>
                ))}
              </div>
            </div>
          )}

          {strongEntries.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-1.5">Strong areas</div>
              <div className="flex flex-wrap gap-1.5">
                {strongEntries.slice(0, 5).map(([topic, score]) => (
                  <span key={topic} className="text-xs bg-green-50 text-green-600 px-2.5 py-1 rounded-full">
                    {topic.replace(/_/g, " ")} · {Math.round(score * 100)}%
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <button
          onClick={onGenerate}
          className="w-full bg-brand text-white py-3 rounded-xl font-medium text-sm hover:bg-green-700 transition"
        >
          🧠 Generate personalized questions
        </button>
        <p className="text-xs text-slate-400 mt-2">AI will create 20 new questions focused on your weak areas</p>
      </div>
    </div>
  );
}
