import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export default async function HomePage() {
  const jar = await cookies();
  redirect(jar.get("refreshToken") ? "/dashboard" : "/login");
}
