import { memo, useEffect, useId, useRef, useState } from "react";
import { searchLocations, type LocationSuggestion } from "../lib/api";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { Input, Label } from "./ui/primitives";

const MIN_QUERY_CHARS = 2;
const DEBOUNCE_MS = 300;
const MAX_SUGGESTIONS = 5;

// Simple in-memory cache so repeated queries don't hit the API.
const queryCache = new Map<string, LocationSuggestion[]>();

export function LocationAutocomplete({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([]);
  const [highlight, setHighlight] = useState(-1);
  const [focused, setFocused] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const suppressFetch = useRef(false);
  const listId = useId();
  const inputId = useId();
  const debouncedQuery = useDebouncedValue(value.trim(), DEBOUNCE_MS);

  // Debounced lookup; aborts stale requests.
  useEffect(() => {
    if (suppressFetch.current) {
      suppressFetch.current = false;
      return;
    }
    if (debouncedQuery.length < MIN_QUERY_CHARS) {
      setSuggestions([]);
      setLoading(false);
      setLoadError(null);
      return;
    }
    const cached = queryCache.get(debouncedQuery);
    if (cached) {
      setSuggestions(cached);
      setHighlight(cached.length ? 0 : -1);
      if (focused) setOpen(true);
      return;
    }
    let cancelled = false;
    const ctrl = new AbortController();
    setLoading(true);
    setLoadError(null);
    (async () => {
      try {
        const out = await searchLocations(debouncedQuery, MAX_SUGGESTIONS, ctrl.signal);
        if (cancelled || !focused) return;
        queryCache.set(debouncedQuery, out);
        setSuggestions(out);
        setHighlight(out.length ? 0 : -1);
        setOpen(true);
      } catch (e) {
        if (ctrl.signal.aborted || cancelled) return;
        setSuggestions([]);
        setLoadError(e instanceof Error ? e.message : "Location search failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      ctrl.abort();
    };
  }, [debouncedQuery, focused]);

  // Close on outside click.
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function pick(s: LocationSuggestion) {
    suppressFetch.current = true;
    onChange(s.display_name);
    setSuggestions([]);
    setOpen(false);
    setHighlight(-1);
  }

  const showEmpty =
    open && focused && !loading && !loadError && value.trim().length >= MIN_QUERY_CHARS && suggestions.length === 0;

  return (
    <div ref={boxRef} className="relative">
      <Label htmlFor={inputId}>{label}</Label>
      <Input
        id={inputId}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-haspopup="listbox"
        aria-activedescendant={
          highlight >= 0 ? `${listId}-opt-${highlight}` : undefined
        }
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          setFocused(true);
          if (suggestions.length) setOpen(true);
        }}
        onBlur={() => setFocused(false)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" && suggestions.length) {
            e.preventDefault();
            setHighlight((h) => (h + 1) % suggestions.length);
          } else if (e.key === "ArrowUp" && suggestions.length) {
            e.preventDefault();
            setHighlight((h) => (h - 1 + suggestions.length) % suggestions.length);
          } else if (e.key === "Enter" && open && highlight >= 0 && suggestions[highlight]) {
            e.preventDefault();
            pick(suggestions[highlight]);
          } else if (e.key === "Escape") {
            setOpen(false);
            setHighlight(-1);
          }
        }}
        required
        placeholder={placeholder}
        autoComplete="off"
      />
      {loading && (
        <div aria-live="polite" className="pointer-events-none absolute right-3 top-8 text-xs text-slate-500">
          Searching…
        </div>
      )}
      {loadError && !loading && (
        <div aria-live="polite" className="mt-1 text-xs text-red-600">
          {loadError}
        </div>
      )}
      {open && suggestions.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="autocomplete-dropdown absolute mt-1 max-h-60 w-full overflow-auto rounded-md border border-slate-200 bg-white shadow-lg"
        >
          {suggestions.map((s, i) => (
            <li
              key={`${s.display_name}-${s.lat}-${s.lon}`}
              id={`${listId}-opt-${i}`}
              role="option"
              aria-selected={i === highlight}
            >
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(s);
                }}
                onMouseEnter={() => setHighlight(i)}
                className={`block w-full truncate px-3 py-2 text-left text-sm hover:bg-teal-50 ${
                  i === highlight ? "bg-teal-50" : ""
                }`}
                title={s.display_name}
              >
                {s.display_name}
              </button>
            </li>
          ))}
          <li className="border-t px-3 py-1 text-[11px] text-slate-400">Suggestions: © OpenStreetMap contributors (Nominatim)</li>
        </ul>
      )}
      {showEmpty && (
        <div className="autocomplete-dropdown absolute mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-lg">
          No matches found.
        </div>
      )}
    </div>
  );
}
