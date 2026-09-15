import Link from "next/link";

const modules = [
  /* __MODULE_LINKS__ */
];

export default function Home() {
  return (
    <main className="min-h-screen bg-neutral-50 text-neutral-950">
      <section className="mx-auto flex min-h-[78vh] max-w-6xl flex-col justify-center px-6 py-16">
        <div className="max-w-3xl">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-emerald-700">
            __APP_TITLE__
          </p>
          <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-normal sm:text-6xl">
            A focused product MVP, ready to shape around real users.
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-neutral-700">
            Launch with a clear user flow, useful backend endpoints, and deployment
            files already in place. Replace this screen with your product brief or
            extend it with the generated modules below.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#contact"
              className="inline-flex h-11 items-center justify-center rounded-md bg-neutral-950 px-5 text-sm font-semibold text-white transition hover:bg-neutral-800"
            >
              Get Started
            </a>
            <a
              href="#features"
              className="inline-flex h-11 items-center justify-center rounded-md border border-neutral-300 px-5 text-sm font-semibold text-neutral-900 transition hover:border-neutral-500"
            >
              View Features
            </a>
          </div>
        </div>
      </section>

      <section id="features" className="border-y border-neutral-200 bg-white">
        <div className="mx-auto grid max-w-6xl gap-4 px-6 py-12 sm:grid-cols-3">
          {["Clear workflow", "Useful data model", "Deployable stack"].map((item) => (
            <div key={item} className="rounded-lg border border-neutral-200 p-5">
              <h2 className="text-base font-semibold">{item}</h2>
              <p className="mt-2 text-sm leading-6 text-neutral-600">
                Built as a practical starting point, with room for the generator to
                add domain-specific screens and backend behavior.
              </p>
            </div>
          ))}
        </div>
      </section>

      {modules.length > 0 && (
        <section className="mx-auto max-w-6xl px-6 py-12">
          <h2 className="text-2xl font-semibold">Product Areas</h2>
          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {modules.map((module: { href: string; label: string }) => (
              <Link
                key={module.href}
                href={module.href}
                className="rounded-lg border border-neutral-200 bg-white p-5 text-sm font-semibold transition hover:border-neutral-400"
              >
                {module.label}
              </Link>
            ))}
          </div>
        </section>
      )}

      <section id="contact" className="mx-auto max-w-6xl px-6 py-12">
        <div className="rounded-lg bg-neutral-950 p-6 text-white sm:p-8">
          <h2 className="text-2xl font-semibold">Ready for the first users</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-300">
            Connect this call to action to the generated lead, booking, checkout, or
            dashboard flow that matches your product brief.
          </p>
        </div>
      </section>
    </main>
  );
}
