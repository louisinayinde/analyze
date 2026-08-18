import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH } from "@/features/auth/cookie";
import { requireInternalApiUrl } from "@/features/auth/backend-url";

// Symétrique de connexion/refresh (J3, backlog.md) : révoque le refresh
// token courant côté back puis efface le cookie. Le cookie est toujours
// effacé, même si l'appel au backend échoue (panne réseau) — un logout ne
// doit jamais laisser l'utilisateur bloqué dans un état "connecté" côté
// front à cause d'un problème purement serveur ; le refresh token laissé
// vivant côté back expire de toute façon à son terme normal (C6).
export async function POST() {
  const magasinCookies = await cookies();
  const refreshToken = magasinCookies.get(REFRESH_COOKIE_NAME)?.value;

  if (refreshToken) {
    await fetch(`${requireInternalApiUrl()}/auth/deconnexion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => undefined);
  }

  const reponse = new NextResponse(null, { status: 204 });
  reponse.cookies.delete({ name: REFRESH_COOKIE_NAME, path: REFRESH_COOKIE_PATH });
  return reponse;
}
