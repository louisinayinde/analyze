"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { connecter, deconnecter, rafraichir } from "./auth-client";
import type { JetonReponse, ResultatAppel } from "./auth-client";
import { getAccessToken, subscribe } from "./token-store";

// "loading" : rafraîchissement silencieux initial en cours (au montage,
// avant de savoir si le cookie httpOnly porte une session valide).
// "authenticated"/"anonymous" : état stable une fois cette première
// vérification terminée. La protection de route (J4, `route-protegee.tsx`)
// s'appuie sur ce statut pour ne rediriger qu'une fois "loading" écoulé —
// jamais sur un accessToken seul, qui vaut aussi `null` pendant le chargement.
type StatutAuth = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  accessToken: string | null;
  status: StatutAuth;
  login: (email: string, motDePasse: string) => Promise<ResultatAppel<JetonReponse>>;
  logout: () => Promise<ResultatAppel<undefined>>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

// Marge de sécurité avant l'expiration réelle de l'access token (15 min par
// défaut, C4/back/src/shared/config.py) : on rafraîchit un peu en avance
// pour ne jamais présenter un jeton expiré à une requête déjà en vol.
const MARGE_SECURITE_SECONDES = 30;
const DELAI_MINIMUM_SECONDES = 5;

type MinuteurRef = React.MutableRefObject<ReturnType<typeof setTimeout> | undefined>;

// Fonction de module (pas un `useCallback`) : elle se rappelle elle-même
// dans son propre `setTimeout` pour planifier le rafraîchissement suivant.
// Une version mémoïsée par `useCallback` se recréerait à chaque rendu et
// s'auto-référencerait avant d'être réassignée (TDZ) — une simple fonction
// récursive hors composant évite le problème et reste plus lisible.
function planifierRafraichissement(
  expiresIn: number,
  minuteurRef: MinuteurRef,
  setStatus: (status: StatutAuth) => void,
): void {
  if (minuteurRef.current) clearTimeout(minuteurRef.current);
  const delaiMs = Math.max(expiresIn - MARGE_SECURITE_SECONDES, DELAI_MINIMUM_SECONDES) * 1000;
  minuteurRef.current = setTimeout(async () => {
    const resultat = await rafraichir();
    if (resultat.data) {
      setStatus("authenticated");
      planifierRafraichissement(resultat.data.expiresIn, minuteurRef, setStatus);
    } else {
      setStatus("anonymous");
    }
  }, delaiMs);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const accessToken = useSyncExternalStore(subscribe, getAccessToken, () => null);
  const [status, setStatus] = useState<StatutAuth>("loading");
  const minuteurRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const tenteRef = useRef(false);

  // Restaure une session existante au montage (rechargement de page, nouvel
  // onglet) : le seul indice disponible côté client est le cookie httpOnly,
  // invisible en JS — on ne peut que tenter le refresh et observer le
  // résultat (J3, backlog.md).
  //
  // `tenteRef` empêche un double appel : en dev, `StrictMode` (activé par
  // défaut sur App Router) monte/démonte/remonte ce composant, et deux
  // appels concurrents partiraient avec le *même* cookie pas encore tourné
  // (la rotation ne s'applique qu'à la réponse du premier) — le second
  // serait détecté comme un rejeu (C6) et révoquerait toute la famille de
  // jetons dès le premier chargement de page.
  useEffect(() => {
    if (tenteRef.current) return;
    tenteRef.current = true;

    let annule = false;
    rafraichir().then((resultat) => {
      if (annule) return;
      if (resultat.data) {
        setStatus("authenticated");
        planifierRafraichissement(resultat.data.expiresIn, minuteurRef, setStatus);
      } else {
        setStatus("anonymous");
      }
    });
    return () => {
      annule = true;
      // Lit volontairement la valeur *courante* de la ref, pas une copie
      // capturée au montage : `login` peut avoir replanifié un minuteur plus
      // récent entre-temps, c'est celui-là qu'il faut annuler.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      if (minuteurRef.current) clearTimeout(minuteurRef.current);
    };
  }, []);

  const login = useCallback(async (email: string, motDePasse: string) => {
    const resultat = await connecter(email, motDePasse);
    if (resultat.data) {
      setStatus("authenticated");
      planifierRafraichissement(resultat.data.expiresIn, minuteurRef, setStatus);
    }
    return resultat;
  }, []);

  const logout = useCallback(async () => {
    const resultat = await deconnecter();
    if (minuteurRef.current) clearTimeout(minuteurRef.current);
    setStatus("anonymous");
    return resultat;
  }, []);

  const value = useMemo(
    () => ({ accessToken, status, login, logout }),
    [accessToken, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
