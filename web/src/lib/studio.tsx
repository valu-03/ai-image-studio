import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkRecent,
  describe,
  fixPhoto,
  getCards,
  getLook,
  getPhoto,
  getPrice,
  getRecent,
  getSettings,
  makePhoto,
  ratePhoto,
  setCard,
  setKey,
  setSettings,
  type GiveawayItem,
  type KeyName,
  type LookCard,
  type LookSnapshot,
  type PhotoJob,
  type PriceEstimate,
  type RecentPhoto,
  type SettingsPayload,
  type SubjectKind,
} from "./api";
import type { ReferenceFile } from "../pages/studio/Reference";

export function useStudio() {
  const initialParams =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search)
      : new URLSearchParams();
  const [text, setTextState] = useState(() => initialParams.get("text") ?? "");
  const [kind, setKind] = useState<SubjectKind>("animal");
  const [cards, setCards] = useState<LookCard[]>([]);
  const [look, setLook] = useState<LookSnapshot>({
    kind: "animal",
    cards: {},
    touched: [],
  });
  const [settings, setSettingsState] = useState<SettingsPayload | null>(null);
  const [price, setPrice] = useState<PriceEstimate | null>(null);
  const [reference, setReference] = useState<ReferenceFile | null>(null);
  const [jobId, setJobId] = useState<string | null>(
    () => initialParams.get("photo") ?? null
  );
  const [job, setJob] = useState<PhotoJob | null>(() => {
    const stageParam = initialParams.get("stage");
    if (stageParam) {
      return {
        state: "running",
        stage: stageParam,
        error: "",
        file_url: null,
        history_id: null,
        giveaways: null,
        check_error: "",
      };
    }
    return null;
  });
  const [pending, setPending] = useState(() => Boolean(initialParams.get("stage")));
  const [recent, setRecent] = useState<RecentPhoto[]>([]);
  const [selectedRecent, setSelectedRecent] = useState<RecentPhoto | null>(null);
  const [recentCheck, setRecentCheck] = useState<{
    historyId: string;
    loading: boolean;
    giveaways: GiveawayItem[] | null;
    check_error: string;
  } | null>(null);

  const inFlightRef = useRef(false);
  const provider = settings?.provider ?? "kie";

  const refreshLookAndCards = useCallback(async (targetKind: SubjectKind) => {
    const [cardList, lookSnap] = await Promise.all([
      getCards(targetKind),
      getLook(),
    ]);
    setCards(cardList);
    setLook(lookSnap);
    setKind(lookSnap.kind);
  }, []);

  const refreshRecent = useCallback(async () => {
    try {
      const list = await getRecent();
      setRecent(list);
    } catch {
      // ignore background poll errors
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const [s, l] = await Promise.all([getSettings(), getLook()]);
        setSettingsState(s);
        setLook(l);
        setKind(l.kind);
        const [c, p, r] = await Promise.all([
          getCards(l.kind),
          getPrice(s.provider),
          getRecent(),
        ]);
        setCards(c);
        setPrice(p);
        setRecent(r);
        if (jobId) {
          const snap = await getPhoto(jobId);
          setJob(snap);
          setPending(snap.state === "running");
        }
      } catch {
        // initial load
      }
    })();
  }, []);

  useEffect(() => {
    if (!settings) return;
    void getPrice(settings.provider)
      .then(setPrice)
      .catch(() => {});
  }, [settings?.provider]);

  // Debounce 600 ms on text changes -> describe()
  useEffect(() => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const timer = setTimeout(() => {
      void (async () => {
        try {
          const res = await describe(trimmed);
          if (res.kind !== kind) {
            await refreshLookAndCards(res.kind);
          }
        } catch {
          // ignore
        }
      })();
    }, 600);
    return () => clearTimeout(timer);
  }, [text, kind, refreshLookAndCards]);

  // Poll running photo job every 1.5 s
  useEffect(() => {
    if (!jobId || !pending) return;
    let active = true;
    const poll = async () => {
      try {
        const status = await getPhoto(jobId);
        if (!active) return;
        setJob(status);
        if (status.state === "done" || status.state === "error") {
          setPending(false);
          inFlightRef.current = false;
          void refreshRecent();
        }
      } catch (err) {
        if (!active) return;
        setJob({
          state: "error",
          stage: "",
          error: err instanceof Error ? err.message : "Could not check photo status.",
          file_url: null,
          history_id: null,
          giveaways: null,
          check_error: "",
        });
        setPending(false);
        inFlightRef.current = false;
      }
    };
    void poll();
    const interval = setInterval(() => void poll(), 1500);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [jobId, pending, refreshRecent]);

  // Poll recent every 10 s
  useEffect(() => {
    const interval = setInterval(() => void refreshRecent(), 10000);
    return () => clearInterval(interval);
  }, [refreshRecent]);

  const selectCardOption = useCallback(async (cardId: string, optionKey: string) => {
    try {
      const updated = await setCard(cardId, optionKey);
      setLook(updated);
    } catch {
      // ignore
    }
  }, []);

  const make = useCallback(async () => {
    if (inFlightRef.current || pending || !text.trim()) return;
    inFlightRef.current = true;
    setPending(true);
    setSelectedRecent(null);
    setRecentCheck(null);
    setJob({
      state: "running",
      stage: "Starting photo generation…",
      error: "",
      file_url: null,
      history_id: null,
      giveaways: null,
      check_error: "",
    });
    try {
      const res = await makePhoto({
        text: text.trim(),
        provider,
        ...(reference && provider !== "higgsfield"
          ? { reference_b64: reference.b64, reference_name: reference.name }
          : {}),
      });
      setJobId(res.id);
    } catch (err) {
      inFlightRef.current = false;
      setPending(false);
      setJob({
        state: "error",
        stage: "",
        error: err instanceof Error ? err.message : "Photo generation failed.",
        file_url: null,
        history_id: null,
        giveaways: null,
        check_error: "",
      });
    }
  }, [pending, text, provider, reference]);

  const fix = useCallback(
    async (giveawayKey: string) => {
      if (inFlightRef.current || pending || !jobId) return;
      inFlightRef.current = true;
      setPending(true);
      setSelectedRecent(null);
      setRecentCheck(null);
      setJob((prev) =>
        prev
          ? { ...prev, state: "running", stage: "Applying fix and remaking photo…", error: "" }
          : null
      );
      try {
        const res = await fixPhoto(jobId, giveawayKey);
        const updatedLook = await getLook();
        setLook(updatedLook);
        setJobId(res.id);
      } catch (err) {
        inFlightRef.current = false;
        setPending(false);
        setJob((prev) =>
          prev
            ? {
                ...prev,
                state: "error",
                stage: "",
                error: err instanceof Error ? err.message : "Could not run Fix.",
              }
            : null
        );
      }
    },
    [pending, jobId]
  );

  const rateCurrentOrRecent = useCallback(
    async (photoId: string | null, thumb: "up" | "down") => {
      if (!photoId) return;
      try {
        await ratePhoto(photoId, thumb);
        await refreshRecent();
      } catch {
        // ignore
      }
    },
    [refreshRecent]
  );

  const runCheckOnRecent = useCallback(async (historyId: string) => {
    setRecentCheck({
      historyId,
      loading: true,
      giveaways: null,
      check_error: "",
    });
    try {
      const res = await checkRecent(historyId);
      setRecentCheck({
        historyId,
        loading: false,
        giveaways: res.giveaways,
        check_error: res.check_error,
      });
    } catch (err) {
      setRecentCheck({
        historyId,
        loading: false,
        giveaways: null,
        check_error: err instanceof Error ? err.message : "Check failed.",
      });
    }
  }, []);

  const saveApiKey = useCallback(async (name: KeyName, value: string) => {
    await setKey(name, value);
    const updated = await getSettings();
    setSettingsState(updated);
  }, []);

  const changeProvider = useCallback(async (nextProvider: "kie" | "higgsfield") => {
    const updated = await setSettings({ provider: nextProvider });
    setSettingsState(updated);
  }, []);

  const toggleLocalApi = useCallback(async (enabled: boolean) => {
    const updated = await setSettings({ local_api_enabled: enabled });
    setSettingsState(updated);
  }, []);

  const keyMissing = settings
    ? provider === "kie"
      ? !settings.keys.KIE_API_KEY
      : !settings.keys.HIGGSFIELD_API_KEY_ID || !settings.keys.HIGGSFIELD_API_KEY_SECRET
    : false;

  return {
    text,
    setText: setTextState,
    kind,
    cards,
    look,
    price,
    provider,
    reference,
    setReference,
    jobId,
    job,
    pending,
    keyMissing,
    recent,
    selectedRecent,
    setSelectedRecent,
    recentCheck,
    settings,
    selectCardOption,
    make,
    fix,
    rateCurrentOrRecent,
    runCheckOnRecent,
    saveApiKey,
    changeProvider,
    toggleLocalApi,
  };
}
