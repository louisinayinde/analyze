import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import {
  refreshCookieOptions,
  REFRESH_COOKIE_NAME,
  REFRESH_COOKIE_PATH,
} from "@/features/auth/cookie";
import { requireInternalApiUrl } from "@/shared/api/internal-url";

// Rafraîchissement silencieux (J3, backlog.md) : lit le refresh token dans
// le cookie httpOnly (jamais transmis par le client — il ne le connaît
// pas), l'échange contre une nouvelle paire côté back (rotation, C6) et
// repose un nouveau cookie. Appelé par `AuthProvider` au montage (restaurer
// une session après rechargement de page) et sur un minuteur avant
// l'expiration de l'access token courant.
export async function POST() {
  const magasinCookies = await cookies();
  const refreshToken = magasinCookies.get(REFRESH_COOKIE_NAME)?.value;

  if (!refreshToken) {
    return NextResponse.json(
      { code: "non_authentifie", message: "Aucune session active.", correlation_id: "" },
      { status: 401 },
    );
  }

  const reponseBackend = await fetch(`${requireInternalApiUrl()}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const donnees = await reponseBackend.json().catch(() => undefined);

  if (!reponseBackend.ok) {
    // Refresh expiré, révoqué, ou rejoué (C6 détecte le rejeu et invalide
    // toute la famille côté back) : ce cookie ne redeviendra jamais valide,
    // on l'efface pour ne pas retenter indéfiniment le même jeton mort.
    const reponse = NextResponse.json(donnees, { status: reponseBackend.status });
    reponse.cookies.delete({ name: REFRESH_COOKIE_NAME, path: REFRESH_COOKIE_PATH });
    return reponse;
  }

  const reponse = NextResponse.json({
    access_token: donnees.access_token,
    expires_in: donnees.expires_in,
    token_type: donnees.token_type,
  });
  reponse.cookies.set(REFRESH_COOKIE_NAME, donnees.refresh_token, refreshCookieOptions());
  return reponse;
}
