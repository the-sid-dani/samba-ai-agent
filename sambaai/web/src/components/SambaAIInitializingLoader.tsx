import { Logo } from "./logo/Logo";
import { useContext } from "react";
import { SettingsContext } from "./settings/SettingsProvider";

export function SambaAIInitializingLoader() {
  const settings = useContext(SettingsContext);

  return (
    <div className="mx-auto my-auto animate-pulse">
      <Logo height={96} width={96} className="mx-auto mb-3" />
      <p className="text-lg text-text font-semibold">
        Initializing {settings?.enterpriseSettings?.application_name ?? "SambaAI"}
      </p>
    </div>
  );
}
