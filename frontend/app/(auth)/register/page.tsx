"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame } from "@/components/auth-frame";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, register } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);

    try {
      await register({
        firstName: String(form.get("firstName")),
        lastName: String(form.get("lastName")),
        email: String(form.get("email")),
        password: String(form.get("password")),
      });
      router.push("/login");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Kayıt oluşturulamadı.");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthFrame
      title="Kayıt"
      description="Ad, soyad, e-posta ve en az 8 karakterlik bir şifre yeterli."
      footer={
        <>
          Zaten hesabın var mı?{" "}
          <Link className="text-[#14221b] underline" href="/login">
            Giriş yap
          </Link>
        </>
      }
    >
      <Card>
        <CardContent>
          <form className="grid gap-4" onSubmit={onSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-1.5 text-sm">
                Ad
                <Input name="firstName" autoComplete="given-name" required />
              </label>
              <label className="grid gap-1.5 text-sm">
                Soyad
                <Input name="lastName" autoComplete="family-name" required />
              </label>
            </div>
            <label className="grid gap-1.5 text-sm">
              E-posta
              <Input name="email" type="email" autoComplete="email" required />
            </label>
            <label className="grid gap-1.5 text-sm">
              Şifre
              <Input name="password" type="password" autoComplete="new-password" minLength={8} required />
            </label>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button className="h-10 w-full" type="submit" disabled={pending}>
              {pending ? "Kaydediliyor" : "Hesap oluştur"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </AuthFrame>
  );
}
