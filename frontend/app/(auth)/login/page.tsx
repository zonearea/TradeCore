"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame } from "@/components/auth-frame";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);

    try {
      await login(String(form.get("email")), String(form.get("password")));
      router.push("/dashboard");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Giriş yapılamadı.");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthFrame
      title="Giriş"
      description="E-posta ve şifrenle oturum aç. Refresh token HttpOnly çerezde kalır."
      footer={
        <>
          Hesabın yok mu?{" "}
          <Link className="text-[#14221b] underline" href="/register">
            Kayıt ol
          </Link>
        </>
      }
    >
      <Card>
        <CardContent>
          <form className="grid gap-4" onSubmit={onSubmit}>
            <label className="grid gap-1.5 text-sm">
              E-posta
              <Input name="email" type="email" autoComplete="email" required />
            </label>
            <label className="grid gap-1.5 text-sm">
              Şifre
              <Input name="password" type="password" autoComplete="current-password" required />
            </label>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button className="h-10 w-full" type="submit" disabled={pending}>
              {pending ? "Giriş yapılıyor" : "Giriş yap"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </AuthFrame>
  );
}
