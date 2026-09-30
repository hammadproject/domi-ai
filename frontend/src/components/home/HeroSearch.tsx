"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ArrowRight, MagnifyingGlass, MapPin } from "@phosphor-icons/react";

const CITIES = [
  { name: "Austin", label: "Austin, TX" },
  { name: "Dallas", label: "Dallas, TX" },
  { name: "Phoenix", label: "Phoenix, AZ" },
];

export function HeroSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = q.trim();
    router.push(text ? `/explore?q=${encodeURIComponent(text)}` : "/explore");
  };

  return (
    <div>
      <form
        onSubmit={submit}
        role="search"
        className="flex w-full max-w-[560px] items-center gap-2 rounded-full border border-line bg-surface p-1.5 pl-5 shadow-soft transition-shadow focus-within:border-primary focus-within:shadow-lift"
      >
        <MagnifyingGlass size={20} className="shrink-0 text-ink-soft" aria-hidden />
        <label htmlFor="hero-search" className="sr-only">
          Describe the home you are looking for
        </label>
        <input
          id="hero-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={200}
          placeholder="3 bedroom homes in Austin under $550k"
          autoComplete="off"
          className="h-11 min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-muted"
        />
        <button
          type="submit"
          className="inline-flex h-11 shrink-0 items-center gap-2 whitespace-nowrap rounded-full bg-primary px-5 text-sm font-medium text-on-primary transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.98]"
        >
          Find homes <ArrowRight size={16} weight="bold" aria-hidden />
        </button>
      </form>
      <ul className="mt-4 flex flex-wrap gap-2.5" aria-label="Start with a city">
        {CITIES.map((c) => (
          <li key={c.name}>
            <Link
              href={`/explore?city=${c.name}`}
              className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-sage"
            >
              <MapPin size={16} aria-hidden /> {c.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
