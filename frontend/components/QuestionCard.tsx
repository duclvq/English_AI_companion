"use client";
import { useState } from "react";

interface Props {
  question: {
    id: string;
    type: string;
    difficulty: number;
    topic: string;
    question_text: string;
    choices: string[];
  };
  onAnswered: (questionId: string, chosenIndex: number, isCorrect: boolean, correctIndex: number, streak: number) => void;
  onSkipped: (questionId: string, correctIndex: number) => void;
}

const DIFF_LABELS = ["", "Beginner", "Intermediate", "Advanced"];
const DIFF_COLORS = ["", "bg-green-100 text-green-700", "bg-yellow-100 text-yellow-700", "bg-red-100 text-red-700"];

export default function QuestionCard({ question, onAnswered, onSkipped }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<{ is_correct: boolean; correct_index: number; streak: number } | null>(null);
  const [skipped, setSkipped] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleChoice(idx: number) {
    if (selected !== null || submitting || skipped) return;
    setSelected(idx);
    setSubmitting(true);

    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`/api/questions/${question.id}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ chosen_index: idx, time_spent_ms: 0 }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        onAnswered(question.id, idx, data.is_correct, data.correct_index, data.streak);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSkip() {
    if (selected !== null || submitting || skipped) return;
    setSubmitting(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`/api/questions/${question.id}/skip`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSkipped(true);
        setResult({ is_correct: false, correct_index: data.correct_index, streak: data.streak });
        onSkipped(question.id, data.correct_index);
      }
    } finally {
      setSubmitting(false);
    }
  }

  function choiceClass(idx: number) {
    const base = "w-full text-left px-4 py-3.5 rounded-xl border text-sm transition-all duration-200";
    if (result) {
      if (idx === result.correct_index) return `${base} border-green-500 bg-green-50 text-green-700 font-medium`;
      if (idx === selected && !result.is_correct) return `${base} border-red-400 bg-red-50 text-red-600`;
      return `${base} border-slate-200 opacity-50`;
    }
    if (idx === selected) return `${base} border-brand bg-green-50`;
    return `${base} border-slate-200 hover:border-brand hover:bg-green-50/50`;
  }

  const diffLabel = DIFF_LABELS[question.difficulty] || "";
  const diffColor = DIFF_COLORS[question.difficulty] || "";
  const answered = selected !== null || skipped;

  return (
    <div className={`flex flex-col justify-center min-h-screen p-4 snap-start ${result ? (result.is_correct ? "flash-green" : "flash-red") : ""}`}>
      <div className="bg-white rounded-2xl shadow-lg p-6 max-w-lg w-full mx-auto">
        <div className="flex justify-between items-center mb-5">
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${diffColor}`}>{diffLabel}</span>
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">{question.type}</span>
        </div>
        <p className="text-lg font-semibold text-slate-800 mb-6 leading-relaxed">{question.question_text}</p>
        <div className="space-y-3">
          {question.choices.map((c, i) => (
            <button key={i} onClick={() => handleChoice(i)} disabled={answered}
              className={choiceClass(i)}>
              <span className="inline-block w-6 text-slate-400 font-medium">{String.fromCharCode(65 + i)}.</span>
              {c}
            </button>
          ))}
        </div>
        {!answered && (
          <button onClick={handleSkip} disabled={submitting}
            className="w-full mt-4 py-2.5 rounded-xl border border-dashed border-slate-300 text-sm text-slate-400 hover:text-slate-600 hover:border-slate-400 transition-all">
            🤷 I don&apos;t know — show me the answer
          </button>
        )}
        {result && (
          <div className={`mt-4 text-center text-sm font-medium ${result.is_correct ? "text-green-600" : skipped ? "text-amber-500" : "text-red-500"}`}>
            {result.is_correct ? `✓ Correct! Streak: ${result.streak}` : skipped ? "📖 Here's the correct answer" : "✗ Wrong answer"}
          </div>
        )}
      </div>
    </div>
  );
}
