"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface Question {
  id: string;
  type: string;
  difficulty: number;
  topic: string;
  question_text: string;
  choices: string[];
}

export default function OnboardingPage() {
  const router = useRouter();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<{ question_id: string; chosen_index: number }[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/onboarding/questions").then(async (res) => {
      if (res.ok) {
        setQuestions(await res.json());
      }
      setLoading(false);
    });
  }, []);

  function selectChoice(idx: number) {
    if (selected !== null) return;
    setSelected(idx);
    const newAnswers = [...answers, { question_id: questions[current].id, chosen_index: idx }];
    setAnswers(newAnswers);

    setTimeout(() => {
      if (current < questions.length - 1) {
        setCurrent(current + 1);
        setSelected(null);
      } else {
        submitAnswers(newAnswers);
      }
    }, 600);
  }

  async function submitAnswers(ans: typeof answers) {
    setSubmitting(true);
    const res = await apiFetch("/onboarding/submit", {
      method: "POST",
      body: JSON.stringify({ answers: ans }),
    });
    if (res.ok) {
      const data = await res.json();
      setResult(data.level);
      setTimeout(() => router.push("/feed"), 2000);
    }
    setSubmitting(false);
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-pulse text-brand text-lg">Loading quiz...</div>
    </div>
  );

  if (result) return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4 text-center">
      <div className="bg-white rounded-2xl shadow-lg p-8 max-w-sm w-full">
        <div className="text-4xl mb-4">🎯</div>
        <h2 className="text-xl font-bold mb-2">Your level: <span className="text-brand capitalize">{result}</span></h2>
        <p className="text-slate-500 text-sm">Redirecting to your feed...</p>
      </div>
    </div>
  );

  const q = questions[current];
  if (!q) return null;

  const diffLabel = ["", "Beginner", "Intermediate", "Advanced"][q.difficulty] || "";

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4">
      <div className="bg-white rounded-2xl shadow-lg p-6 max-w-md w-full">
        <div className="flex justify-between items-center mb-4">
          <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2 py-1 rounded">{diffLabel}</span>
          <span className="text-xs text-slate-400">{current + 1} / {questions.length}</span>
        </div>
        <p className="text-lg font-semibold text-slate-800 mb-6">{q.question_text}</p>
        <div className="space-y-3">
          {q.choices.map((c, i) => (
            <button key={i} onClick={() => selectChoice(i)} disabled={selected !== null || submitting}
              className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition
                ${selected === i ? "border-brand bg-green-50 text-brand font-medium" : "border-slate-200 hover:border-brand hover:bg-green-50"}
                disabled:opacity-70`}>
              {c}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
