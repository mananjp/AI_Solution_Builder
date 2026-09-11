import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-3xl font-bold">__APP_TITLE__</h1>
        <p className="mt-2 text-slate-600">
          A functional MVP generated from validated solution artifacts by AI Solution Builder.
        </p>
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* __MODULE_LINKS__ */}
        </div>
      </div>
    </main>
  );
}