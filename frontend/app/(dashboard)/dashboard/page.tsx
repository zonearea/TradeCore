"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, currentUser, logout, type CurrentUser } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let active = true;

    currentUser()
      .then((profile) => {
        if (active) {
          setUser(profile);
        }
      })
      .catch((caught) => {
        if (!active) {
          return;
        }

        setError(caught instanceof ApiError ? caught.message : "Profil alınamadı.");
      });

    return () => {
      active = false;
    };
  }, []);

  async function onLogout() {
    setPending(true);
    try {
      await logout();
    } finally {
      router.push("/login");
      router.refresh();
    }
  }

  const name = [user?.firstName, user?.lastName].filter(Boolean).join(" ") || "Kullanıcı";

  return (
    <main className="min-h-screen bg-[#f6f3ee] text-[#17211c]">
      <header className="flex items-center justify-between border-b border-[#e4ddd2] px-6 py-5 sm:px-10">
        <div>
          <p className="text-xs tracking-[0.22em] text-[#5d6b63] uppercase">CleanCore</p>
          <h1 className="font-heading text-2xl">{name}</h1>
        </div>
        <Button variant="outline" className="h-10" onClick={onLogout} disabled={pending}>
          {pending ? "Çıkılıyor" : "Çıkış yap"}
        </Button>
      </header>
      <section className="mx-auto grid max-w-5xl gap-4 px-6 py-10 sm:grid-cols-3 sm:px-10">
        <Card>
          <CardHeader>
            <CardDescription>Hesap</CardDescription>
            <CardTitle>{user?.email ?? "—"}</CardTitle>
          </CardHeader>
          <CardContent>GET /api/auth/me üzerinden okundu.</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Rol</CardDescription>
            <CardTitle>{user?.role ?? "—"}</CardTitle>
          </CardHeader>
          <CardContent>Access token çerezindeki rol bilgisi.</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Oturum</CardDescription>
            <CardTitle>{error ? "Kapalı" : user ? "Aktif" : "Yükleniyor"}</CardTitle>
          </CardHeader>
          <CardContent>{error ?? "Refresh token 7 gün, access token 15 dakika."}</CardContent>
        </Card>
      </section>
    </main>
  );
}
