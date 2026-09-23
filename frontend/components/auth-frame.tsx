import Link from "next/link";
import type { ReactNode } from "react";

export function AuthFrame({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_0.9fr]">
      <section className="hidden flex-col justify-between bg-[#14221b] px-12 py-10 text-[#f4f1ea] lg:flex">
        <p className="text-sm tracking-[0.22em] uppercase">CleanCore</p>
        <div className="max-w-md">
          <h1 className="font-heading text-5xl leading-tight">Katmanlar ayrı, oturum çerezde.</h1>
          <p className="mt-4 text-base text-[#d7e2da]">
            Access ve refresh token tarayıcı belleğine yazılmaz. HttpOnly çerezler API yanıtıyla gelir.
          </p>
        </div>
        <p className="text-sm text-[#9eb0a6]">PostgreSQL · .NET 9 · Next.js 15</p>
      </section>
      <section className="flex items-center justify-center bg-[#f6f3ee] px-6 py-12">
        <div className="w-full max-w-md">
          <p className="mb-6 text-sm tracking-[0.22em] text-[#5d6b63] uppercase lg:hidden">CleanCore</p>
          <h2 className="font-heading text-3xl text-[#17211c]">{title}</h2>
          <p className="mt-2 text-sm text-[#5d6b63]">{description}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-6 text-sm text-[#5d6b63]">{footer}</p>
          <p className="sr-only">
            <Link href="/">Ana sayfa</Link>
          </p>
        </div>
      </section>
    </main>
  );
}
