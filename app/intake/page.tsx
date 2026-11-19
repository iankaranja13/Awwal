"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { TOPICS } from "@/lib/intake";
import { useStore, useT } from "@/lib/store";
import type { Answer, Answers, Question } from "@/lib/types";
import { Button, Chip, useRequire } from "@/components/ui";

const visible = (q: Question, a: Answers) =>
  q.kind !== "choice" || !q.showIf || a[q.showIf.id]?.value === q.showIf.equals;

export default function IntakePage() {
  const { consent, answers, setAnswer, topicIndex, setTopicIndex, runAssessment } = useStore();
  const { t, L } = useT();
  const router = useRouter();
  const [dir, setDir] = useState(1);
  const ok = useRequire(consent.intake, "/consent");
  if (!ok) return null;

  const topic = TOPICS[topicIndex];
  const last = topicIndex === TOPICS.length - 1;
  const questions = topic.questions.filter((q) => visible(q, answers));

  const go = (i: number) => {
    setDir(i > topicIndex ? 1 : -1);
    setTopicIndex(i);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const next = () => {
    // Anything left blank is recorded as skipped, never as "no".
    const final: Answers = { ...answers };
    for (const q of questions) {
      if (!answers[q.id]) {
        final[q.id] = { status: "skipped" };
        setAnswer(q.id, { status: "skipped" });
      }
    }
    if (last) {
      const r = runAssessment(final);
      router.push(r.route === "URGENT" ? "/next" : "/results");
      return;
    }
    go(topicIndex + 1);
  };

  const back = () => (topicIndex === 0 ? router.push("/consent") : go(topicIndex - 1));

  const choose = (q: Question, a: Answer) => {
    const cur = answers[q.id];
    const same = cur && cur.status === a.status && cur.value === a.value;
    setAnswer(q.id, same ? undefined : a);
    if (q.id === "ttc" && a.value !== "trying") setAnswer("ttc_months", undefined);
  };

  return (
    <div className="grid flex-1 gap-12 py-10 lg:grid-cols-12 lg:gap-20 lg:py-16">
      {/* Topic stepper: the user's path through the intake */}
      <nav aria-label="Progress" className="lg:sticky lg:top-12 lg:col-span-4 lg:self-start">
        <div className="relative hidden lg:block">
          <div aria-hidden className="absolute inset-y-5 start-[0.3rem] w-0.5 rounded-full bg-line">
            <motion.div
              className="absolute inset-x-0 top-0 rounded-full bg-saffron"
              animate={{ height: `${(topicIndex / (TOPICS.length - 1)) * 100}%` }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
          <ol className="relative">
            {TOPICS.map((tp, i) => {
              const done = i < topicIndex;
              const now = i === topicIndex;
              return (
                <li key={tp.id}>
                  <button
                    type="button"
                    disabled={i > topicIndex}
                    onClick={() => go(i)}
                    aria-current={now ? "step" : undefined}
                    className="group flex h-10 w-full items-center gap-4 text-start disabled:cursor-default"
                  >
                    <span
                      aria-hidden
                      className={`size-3 rounded-full transition-colors duration-300 ${
                        now ? "bg-pine ring-4 ring-pine-soft" : done ? "bg-pine" : "bg-mist ring-[1.5px] ring-line"
                      }`}
                    />
                    <span
                      className={`text-sm transition-colors ${
                        now ? "font-medium text-ink" : done ? "text-ink group-hover:text-pine" : "text-muted"
                      }`}
                    >
                      {L(tp.title)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>

        {/* Narrow windows: a simple bar */}
        <div className="flex items-center gap-3 lg:hidden">
          <div className="relative h-[3px] flex-1 overflow-hidden rounded-full bg-line">
            <motion.div
              className="absolute inset-y-0 start-0 rounded-full bg-saffron"
              animate={{ width: `${((topicIndex + 1) / TOPICS.length) * 100}%` }}
            />
          </div>
          <span className="text-xs tabular-nums text-muted">
            {topicIndex + 1} {t("of")} {TOPICS.length}
          </span>
        </div>
      </nav>

      <div className="lg:col-span-8">
        <AnimatePresence mode="wait" initial={false}>
          <motion.section
            key={topic.id}
            initial={{ opacity: 0, y: 14 * dir }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -14 * dir }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          >
            <h1 className="display text-xl font-light text-ink md:text-2xl">{L(topic.title)}</h1>
            <p className="mt-3 text-base text-muted">{L(topic.why)}</p>

            <div className="mt-12 divide-y divide-line border-y border-line">
              <AnimatePresence initial={false}>
                {questions.map((q) => (
                  <motion.div
                    key={q.id}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.3 }}
                    className="overflow-hidden"
                  >
                    <QuestionRow
                      q={q}
                      answer={answers[q.id]}
                      onChoose={(a) => choose(q, a)}
                      onNumber={(a) => setAnswer(q.id, a)}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </motion.section>
        </AnimatePresence>

        <div className="mt-10 flex items-center justify-between gap-3">
          <Button variant="quiet" onClick={back}>
            {t("back")}
          </Button>
          <Button onClick={next}>{last ? t("seeResults") : t("continue")}</Button>
        </div>
      </div>
    </div>
  );
}

/** Question on the left, answers on the right: reads like a form, scans fast. */
function QuestionRow({
  q,
  answer,
  onChoose,
  onNumber,
}: {
  q: Question;
  answer?: Answer;
  onChoose: (a: Answer) => void;
  onNumber: (a: Answer | undefined) => void;
}) {
  const { t, L } = useT();
  const is = (status: Answer["status"], value?: string) =>
    answer?.status === status && (value === undefined || answer.value === value);

  return (
    <div
      role="group"
      aria-labelledby={`q-${q.id}`}
      className="grid gap-4 py-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:gap-8"
    >
      <p id={`q-${q.id}`} className="text-base text-ink">
        {L(q.label)}
      </p>
      <div className="flex flex-wrap items-center gap-2 md:justify-end">
        {q.kind === "choice" ? (
          q.options.map((o) => (
            <Chip key={o.value} selected={is("answered", o.value)} onClick={() => onChoose({ status: "answered", value: o.value })}>
              {L(o.label)}
            </Chip>
          ))
        ) : (
          <NumberField q={q} answer={answer} onChange={onNumber} />
        )}
        <span className="inline-flex gap-1">
          <Chip quiet selected={is("unsure")} onClick={() => onChoose({ status: "unsure" })}>
            {t("notSure")}
          </Chip>
          <Chip quiet selected={is("prefer_not")} onClick={() => onChoose({ status: "prefer_not" })}>
            {t("preferNot")}
          </Chip>
        </span>
      </div>
    </div>
  );
}

function NumberField({
  q,
  answer,
  onChange,
}: {
  q: Extract<Question, { kind: "number" }>;
  answer?: Answer;
  onChange: (a: Answer | undefined) => void;
}) {
  const { t, L } = useT();
  const [text, setText] = useState(answer?.status === "answered" ? String(answer.value) : "");
  const [error, setError] = useState(false);

  const commit = (v: string) => {
    if (v.trim() === "") {
      setError(false);
      if (answer?.status === "answered") onChange(undefined);
      return;
    }
    const n = Number(v.replace(",", "."));
    const bad = Number.isNaN(n) || n < q.min || n > q.max;
    setError(bad);
    onChange(bad ? undefined : { status: "answered", value: n });
  };

  return (
    <div className="relative">
      <div
        className={`flex h-10 w-36 items-center rounded-full bg-paper px-4 ring-1 transition-shadow focus-within:ring-2 ${
          error ? "ring-alarm" : answer?.status === "answered" ? "ring-pine" : "ring-line focus-within:ring-pine"
        }`}
      >
        <input
          inputMode="decimal"
          aria-label={L(q.label)}
          aria-invalid={error}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (answer && answer.status !== "answered") onChange(undefined);
          }}
          onBlur={(e) => commit(e.target.value)}
          className="w-full bg-transparent text-sm text-ink tabular-nums outline-none"
        />
        <span className="ms-2 text-sm text-muted">{L(q.unit)}</span>
      </div>
      {error && (
        <p role="alert" className="absolute mt-1 whitespace-nowrap text-xs text-alarm">
          {t("invalidNumber")} {q.min} {t("and")} {q.max}
        </p>
      )}
    </div>
  );
}
