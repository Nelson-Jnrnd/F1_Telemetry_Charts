import catalog from "../data/driverPortraits.json";

type PortraitEntry = {
  path: string;
};

type PortraitCatalog = {
  entries: Record<string, Record<string, PortraitEntry>>;
};

const portraitCatalog = catalog as PortraitCatalog;

export function driverPortraitUrl(season: number | undefined, driver: string): string | null {
  if (!season || !driver) return null;
  return portraitCatalog.entries[String(season)]?.[driver.toUpperCase()]?.path ?? null;
}
