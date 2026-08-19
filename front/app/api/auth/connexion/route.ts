import { NextResponse } from "next/server";
import { refreshCookieOptions, REFRESH_COOKIE_NAME } from "@/features/auth/cookie";
import { requireInternalApiUrl } from "@/shared/api/internal-url";

// BFF (J3, backlog.md) : seul endroit qui voit le refresh token en clair
// côté front. Le navigateur n'appelle jamais `POST /auth/connexion` du
// backend directement — sinon le refresh token atteindrait le JS client via
// la réponse JSON, quel que soit l'endroit où on le stocke ensuite
// (projets.md : jamais en localStorage, jamais accessible en JS). En
// passant par ce Route Handler (même origine que le navigateur, contrairement
// à l'API FastAPI), le refresh token part uniquement dans un Set-Cookie
// httpOnly — jamais dans le corps renvoyé au client.
export async function POST(request: Request) {
  const corps = await request.json();

  const reponseBackend = await fetch(`${requireInternalApiUrl()}/auth/connexion`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  const donnees = await reponseBackend.json().catch(() => undefined);

  if (!reponseBackend.ok) {
    return NextResponse.json(donnees, { status: reponseBackend.status });
  }

  const reponse = NextResponse.json({
    access_token: donnees.access_token,
    expires_in: donnees.expires_in,
    token_type: donnees.token_type,
  });
  reponse.cookies.set(REFRESH_COOKIE_NAME, donnees.refresh_token, refreshCookieOptions());
  return reponse;
}
