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
  return <span className="grid size-11 place-items-center rounded-full bg-sage text-sage-ink">{children}</span>;
}

export default function Home() {
  return (
    <>
      {/* 1. Hero: asymmetric split. Sized so the whole of it (copy, search, city picks, preview)
          is visible on a laptop screen without scrolling. */}
      <section className="mx-auto grid w-full max-w-[1400px] grid-cols-1 items-center gap-8 px-4 pb-10 pt-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-12 lg:pb-12 lg:pt-8">
        <div>
          <Reveal>
            <p className="text-[13px] font-medium uppercase tracking-[0.18em] text-sage-ink">
              Your AI home search companion
            </p>
          </Reveal>
          <Reveal delay={0.08}>
            <h1 className="font-display mt-4 text-5xl font-bold leading-[1.04] text-ink sm:text-6xl lg:text-[3.5rem] xl:text-[4rem]">
              Find a home.
              <br />
              Feel at home.
            </h1>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-4 max-w-[46ch] text-lg leading-relaxed text-ink-soft">
              Tell Domi your budget, city and must-haves. Search in plain words, compare homes, estimate monthly costs.
            </p>
          </Reveal>
          <Reveal delay={0.24} className="mt-6">
            <HeroSearch />
          </Reveal>
        </div>
        <Reveal delay={0.2}>
          <HeroPreview />
        </Reveal>
      </section>

      {/* 2. Bento: one wide cell, one tall map cell that fills its height, one live numbers cell */}
      <section className="mx-auto w-full max-w-[1400px] px-4 py-12 sm:px-8 lg:py-16">
        <Reveal onScroll>
          <h2 className="font-display max-w-[24ch] text-balance text-3xl font-bold leading-tight text-ink sm:text-4xl">
            From a rough idea to a short list.
          </h2>
        </Reveal>
        <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-5 md:grid-rows-[auto_auto]">
          <Reveal onScroll className="rounded-[28px] border border-line bg-sage p-6 sm:p-7 md:col-span-3">
            <IconCircle>
              <ChatCircleDots size={22} aria-hidden />
            </IconCircle>
            <h3 className="font-display mt-4 text-2xl font-bold text-ink sm:text-3xl">Search in your own words</h3>
            <p className="mt-2 max-w-[52ch] text-[16px] leading-relaxed text-ink-soft">
              Describe what you want, like a 3 bedroom in Austin under 500k. Domi turns it into filters and finds
              matching homes.
            </p>
            <ul className="mt-5 flex flex-wrap gap-2.5" aria-label="Try an example search">
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

          <Reveal
            onScroll
            delay={0.1}
            className="relative isolate flex flex-col overflow-hidden rounded-[28px] border border-line bg-primary p-6 text-on-primary sm:p-7 md:col-span-2 md:row-span-2"
          >
            <IconCircle>
              <MapTrifold size={22} aria-hidden />
            </IconCircle>
            <h3 className="font-display mt-4 text-2xl font-bold sm:text-3xl">Explore homes on the map</h3>
            <p className="mt-2 max-w-[40ch] text-[16px] leading-relaxed opacity-90">
              See every match as a price pin. Click one to ask Domi about that home.
            </p>
            <MapCellPreview />
            <LinkButton href="/explore" variant="sage" className="mt-5 self-start">
              Open the map <ArrowRight size={16} weight="bold" aria-hidden />
            </LinkButton>
          </Reveal>

          <Reveal onScroll delay={0.05} className="rounded-[28px] border border-line bg-surface p-6 sm:p-7 md:col-span-3">
            <IconCircle>
              <ChartBar size={22} aria-hidden />
            </IconCircle>
            <h3 className="font-display mt-4 text-2xl font-bold text-ink sm:text-3xl">Understand the numbers</h3>
            <div className="mt-4">
              <PaymentMini />
            </div>
          </Reveal>
        </div>
      </section>

      {/* 3. How it works: sticky heading beside stacked steps */}
      <section className="bg-surface-2/70">
        <div className="mx-auto grid w-full max-w-[1400px] grid-cols-1 gap-8 px-4 py-12 sm:px-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-14 lg:py-16">
          <div className="lg:sticky lg:top-24 lg:self-start">
            <Reveal onScroll>
              <h2 className="font-display text-3xl font-bold leading-tight text-ink sm:text-4xl">
                Your search, made simpler.
              </h2>
              <p className="mt-3 max-w-[36ch] text-lg text-ink-soft">
                Three small moves from a first idea to a shortlist you feel good about.
              </p>
            </Reveal>
          </div>
          <ol className="space-y-3">
            {STEPS.map((s, i) => (
              <Reveal key={s.title} onScroll as="li" delay={i * 0.08} className="flex gap-4 rounded-[24px] border border-line bg-surface p-5 sm:p-6">
                <span className="font-display grid size-12 shrink-0 place-items-center rounded-full bg-sage text-2xl font-bold text-sage-ink">
                  {i + 1}
                </span>
                <div>
                  <h3 className="font-display text-xl font-bold text-ink sm:text-2xl">{s.title}</h3>
                  <p className="mt-1 text-[16px] leading-relaxed text-ink-soft">{s.body}</p>
                </div>
              </Reveal>
            ))}
          </ol>
        </div>
      </section>

      {/* 4. Cities: one large card beside two stacked */}
      <section className="mx-auto w-full max-w-[1400px] px-4 py-12 sm:px-8 lg:py-16">
        <Reveal onScroll>
          <h2 className="font-display text-3xl font-bold text-ink sm:text-4xl">Start with a city.</h2>
        </Reveal>
        <Reveal onScroll className="mt-6" delay={0.08}>
          <CityCards />
        </Reveal>
      </section>

      {/* 5. Closing banner */}
      <section className="mx-auto w-full max-w-[1400px] px-4 pb-12 sm:px-8 lg:pb-16">
        <Reveal onScroll className="relative isolate overflow-hidden rounded-[28px] bg-primary px-6 py-10 text-on-primary sm:px-12 sm:py-12">
          <div aria-hidden className="absolute -right-24 -top-24 size-96 rounded-full bg-on-primary/5" />
          <div aria-hidden className="absolute -bottom-32 right-24 size-80 rounded-full bg-on-primary/5" />
          <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="font-display text-3xl font-bold sm:text-4xl">Your next chapter starts here.</h2>
              <p className="mt-2 text-lg opacity-90">Smarter search. Clearer decisions. A more confident you.</p>
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
