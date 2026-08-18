type ClassValue = string | number | boolean | undefined | null | ClassValue[];

function pushClasses(value: ClassValue, acc: string[]) {
  if (!value) return;
  if (Array.isArray(value)) {
    for (const item of value) pushClasses(item, acc);
    return;
  }
  acc.push(String(value));
}

// Concatène des classes conditionnelles sans dépendance externe (agents.md
// §2) : évite d'ajouter clsx/tailwind-merge pour un besoin qui tient en
// quelques lignes.
export function cn(...values: ClassValue[]): string {
  const acc: string[] = [];
  for (const value of values) pushClasses(value, acc);
  return acc.join(" ");
}
