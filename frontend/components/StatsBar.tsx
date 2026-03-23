"use client";

interface Props {
  streak: number;
  total: number;
  correct: number;
}

export default function StatsBar({ streak, total, correct }: Props) {
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;
  return (
    <div className="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-md z-40 bg-white/90 backdrop-blur border-b border-slate-100">
      <div className="max-w-lg mx-auto flex items-center justify-between px-4 py-2.5">
        <span className="text-sm font-bold text-slate-800">🔥 {streak}</span>
        <span className="text-xs font-semibold text-brand">English AI Companion</span>
        <span className="text-sm font-medium text-slate-500">{accuracy}% · {total} done</span>
      </div>
    </div>
  );
}
