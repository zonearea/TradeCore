/**
 * Ana sayfa — uygulama açılır açılmaz masaüstü kokpite gider.
 * Local-First: oturum çerezi kontrol edilmez.
 */
import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/dashboard");
}
