import Link from "next/link";
import { ArrowRight, ChatCircleDots, MapTrifold, ChartBar } from "@phosphor-icons/react/ssr";
import { CityCards } from "@/components/home/CityCards";
import { HeroPreview } from "@/components/home/HeroPreview";
import { HeroSearch } from "@/components/home/HeroSearch";
import { MapCellPreview } from "@/components/home/MapCellPreview";
import { PaymentMini } from "@/components/home/PaymentMini";
import { LinkButton } from "@/components/ui/Button";
import { Reveal } from "@/components/ui/Reveal";

const PROMPTS = [
  "3 bedroom homes in Austin under $550k",
  "Condos in Phoenix under $300k",
  "Single family homes in Dallas over 2,000 sqft",
];

const STEPS = [
  { title: "Tell Domi what matters", body: "Share your budget, city and must-haves in everyday language." },
  { title: "Refine on the map", body: "Change filters, click pins, and watch the results update together." },
  { title: "Compare your shortlist", body: "Put two or three homes side by side, with estimated monthly costs." },
];

function IconCircle({ children }: { children: React.ReactNode }) {
  return <span className="grid size-12 place-items-center rounded-full bg-sage text-sage-ink">{children}</span>;
}

export default function Home() {
  return (
    <>
      {/* 1. Hero: asymmetric split */}
      <section className="mx-auto grid w-full max-w-[1400px] items-center gap-12 px-4 pb-16 pt-10 sm:px-8 lg:min-h-[calc(100dvh-68px)] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-16 lg:pb-12 lg:pt-12">
        <div>
          <Reveal>
            <p className="text-[13px] font-medium uppercase tracking-[0.18em] text-sage-ink">
              Your AI home search companion
            </p>
          </Reveal>
          <Reveal delay={0.08}>
            <h1 className="font-display mt-5 text-5xl font-bold leading-[1.04] text-ink sm:text-6xl lg:text-[4.25rem]">
              Find a home.
              <br />
              Feel at home.
            </h1>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-6 max-w-[46ch] text-lg leading-relaxed text-ink-soft">
              Tell Domi your budget, city and must-haves. Search in plain words, compare homes, estimate monthly costs.
            </p>
          </Reveal>
          <Reveal delay={0.24} className="mt-8">
            <HeroSearch />
          </Reveal>
        </div>
        <Reveal delay={0.2}>
          <HeroPreview />
        </Reveal>
      </section>

      {/* 2. Bento: one wide cell, one tall map cell, one live numbers cell */}
      <section className="mx-auto w-full max-w-[1400px] px-4 py-16 sm:px-8 lg:py-24">
        <Reveal onScroll>
          <h2 className="font-display max-w-[16ch] text-4xl font-bold leading-tight text-ink sm:text-5xl">
            From a rough idea to a short list.
          </h2>
        </Reveal>
        <div className="mt-10 grid gap-4 md:grid-cols-5 md:grid-rows-[auto_auto]">
          <Reveal onScroll className="rounded-[28px] border border-line bg-sage p-7 md:col-span-3 sm:p-9">
            <IconCircle>
              <ChatCircleDots size={24} aria-hidden />
            </IconCircle>
            <h3 className="font-display mt-6 text-3xl font-bold text-ink">Search in your own words</h3>
            <p className="mt-3 max-w-[52ch] text-[17px] leading-relaxed text-ink-soft">
              Describe what you want, like a 3 bedroom in Austin under 500k. Domi turns it into filters and finds
              matching homes.
            </p>
            <ul className="mt-6 flex flex-wrap gap-2.5" aria-label="Try an example search">
              {PROMPTS.map((p) => (
                <li key={p}>
                  <Link
                    href={`/explore?q=${encodeURIComponent(p)}`}
                    className="inline-flex items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm font-medium text-ink transition-[background-color,transform] hover:bg-canvas active:scale-[0.98]"
                  >
                    {p} <ArrowRight size={14} weight="bold" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal onScroll delay={0.1} className="relative isolate overflow-hidden rounded-[28px] border border-line bg-primary p-7 text-on-primary md:col-span-2 md:row-span-2 sm:p-9">
            <IconCircle>
              <MapTrifold size={24} aria-hidden />
            </IconCircle>
            <h3 className="font-display mt-6 text-3xl font-bold">Explore homes on the map</h3>
            <p className="mt-3 max-w-[40ch] text-[17px] leading-relaxed opacity-90">
              See every match as a price pin. Click one to ask Domi about that home.
            </p>
            <MapCellPreview />
            <LinkButton href="/explore" variant="sage" className="mt-8">
              Open the map <ArrowRight size={16} weight="bold" aria-hidden />
            </LinkButton>
          </Reveal>

          <Reveal onScroll delay={0.05} className="rounded-[28px] border border-line bg-surface p-7 md:col-span-3 sm:p-9">
            <IconCircle>
              <ChartBar size={24} aria-hidden />
            </IconCircle>
            <h3 className="font-display mt-6 text-3xl font-bold text-ink">Understand the numbers</h3>
            <div className="mt-5">
              <PaymentMini />
            </div>
          </Reveal>
        </div>
      </section>

      {/* 3. How it works: sticky heading beside stacked steps */}
      <section className="bg-surface-2/70">
        <div className="mx-auto grid w-full max-w-[1400px] gap-10 px-4 py-16 sm:px-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16 lg:py-24">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <Reveal onScroll>
              <h2 className="font-display text-4xl font-bold leading-tight text-ink sm:text-5xl">
                Your search, made simpler.
              </h2>
              <p className="mt-4 max-w-[36ch] text-lg text-ink-soft">
                Three small moves from a first idea to a shortlist you feel good about.
              </p>
            </Reveal>
          </div>
          <ol className="space-y-4">
            {STEPS.map((s, i) => (
              <Reveal onScroll key={s.title} as="li" delay={i * 0.08} className="flex gap-5 rounded-[28px] border border-line bg-surface p-6 sm:p-8">
                <span className="font-display grid size-14 shrink-0 place-items-center rounded-full bg-sage text-3xl font-bold text-sage-ink">
                  {i + 1}
                </span>
                <div>
                  <h3 className="font-display text-2xl font-bold text-ink">{s.title}</h3>
                  <p className="mt-1.5 text-[17px] leading-relaxed text-ink-soft">{s.body}</p>
                </div>
              </Reveal>
            ))}
          </ol>
        </div>
      </section>

      {/* 4. Cities: one large card beside two stacked */}
      <section className="mx-auto w-full max-w-[1400px] px-4 py-16 sm:px-8 lg:py-24">
        <Reveal onScroll>
          <h2 className="font-display text-4xl font-bold text-ink sm:text-5xl">Start with a city.</h2>
        </Reveal>
        <Reveal onScroll className="mt-10" delay={0.08}>
          <CityCards />
        </Reveal>
      </section>

      {/* 5. Closing banner */}
      <section className="mx-auto w-full max-w-[1400px] px-4 pb-16 sm:px-8 lg:pb-24">
        <Reveal onScroll className="relative isolate overflow-hidden rounded-[32px] bg-primary px-7 py-12 text-on-primary sm:px-14 sm:py-16">
          <div aria-hidden className="absolute -right-24 -top-24 size-96 rounded-full bg-on-primary/5" />
          <div aria-hidden className="absolute -bottom-32 right-24 size-80 rounded-full bg-on-primary/5" />
          <div className="relative flex flex-col gap-8 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="font-display text-4xl font-bold sm:text-5xl">Your next chapter starts here.</h2>
              <p className="mt-3 text-lg opacity-90">Smarter search. Clearer decisions. A more confident you.</p>
            </div>
            <LinkButton href="/explore" variant="sage" size="lg" className="self-start md:self-auto">
              Explore homes <ArrowRight size={18} weight="bold" aria-hidden />
            </LinkButton>
          </div>
        </Reveal>
      </section>
    </>
  );
}
