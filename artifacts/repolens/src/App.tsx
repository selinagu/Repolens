import { FormEvent, useMemo, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAnalyzeRepository, useAskRepository, type RepositoryAnalysis, type RepositoryAnswer } from '@workspace/api-client-react';
import {
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleAlert,
  CircleDot,
  Code2,
  ExternalLink,
  FileCode2,
  FolderTree,
  Github,
  Globe2,
  LoaderCircle,
  MessageSquareText,
  Network,
  Search,
  Sparkles,
  Star,
  Terminal,
} from 'lucide-react';
import { ErrorBoundary } from '@/components/error-boundary';

const queryClient = new QueryClient();

const exampleRepositories = [
  { label: 'Next.js', url: 'https://github.com/vercel/next.js' },
  { label: 'React', url: 'https://github.com/facebook/react' },
];

function isGithubUrl(value: string) {
  try {
    const url = new URL(value.trim());
    const segments = url.pathname.split('/').filter(Boolean);
    return url.protocol === 'https:' && (url.hostname === 'github.com' || url.hostname === 'www.github.com') && segments.length >= 2;
  } catch {
    return false;
  }
}

function errorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { error?: string } } }).response;
    if (response?.data?.error) return response.data.error;
  }
  if (error instanceof Error && error.message) return error.message;
  return 'The repository could not be analyzed. Check the URL and try again.';
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric' }).format(date);
}

function FileRow({ path, kind, description, index }: { path: string; kind: string; description: string; index: number }) {
  const kindColor: Record<string, string> = {
    entry: 'text-[hsl(var(--primary))] bg-[hsl(var(--primary)/.09)]',
    config: 'text-amber-700 bg-amber-50',
    module: 'text-sky-700 bg-sky-50',
    docs: 'text-violet-700 bg-violet-50',
    test: 'text-rose-700 bg-rose-50',
  };
  return (
    <div className="group flex gap-3 border-b border-[hsl(var(--border)/.7)] py-3 last:border-0" data-testid={`row-file-${index}`}>
      <div className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
        <FileCode2 size={13} strokeWidth={1.7} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <code className="truncate font-mono text-[12px] font-medium text-[hsl(var(--foreground))]">{path}</code>
          <span className={`rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[.08em] ${kindColor[kind] ?? 'bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]'}`}>{kind}</span>
        </div>
        <p className="mt-1 text-[12px] leading-5 text-[hsl(var(--muted-foreground))]">{description}</p>
      </div>
      <ChevronRight className="mt-1 hidden shrink-0 text-[hsl(var(--border))] transition-transform group-hover:translate-x-0.5 sm:block" size={15} />
    </div>
  );
}

function EmptyState({ onExample }: { onExample: (url: string) => void }) {
  return (
    <div className="repolens-rise mx-auto max-w-3xl px-4 pb-24 pt-12 sm:px-6 sm:pt-20">
      <div className="mb-8 flex items-center gap-3 text-[hsl(var(--muted-foreground))]">
        <div className="flex size-10 items-center justify-center rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] shadow-sm">
          <Search size={18} className="text-[hsl(var(--primary))]" />
        </div>
        <div className="h-px flex-1 bg-[hsl(var(--border))]" />
        <span className="font-mono text-[10px] uppercase tracking-[.18em]">Read before you build</span>
      </div>
      <h1 className="max-w-2xl text-4xl font-semibold leading-[1.1] tracking-[-.045em] text-[hsl(var(--foreground))] sm:text-5xl">
        Understand the repo.<br />
        <span className="text-[hsl(var(--primary))]">Skip the archaeology.</span>
      </h1>
      <p className="mt-5 max-w-xl text-[15px] leading-7 text-[hsl(var(--muted-foreground))]">
        RepoLens maps the important paths in a public GitHub repository, then stays with you while you trace the decisions behind the code.
      </p>
      <div className="mt-10 grid gap-3 sm:grid-cols-3">
        {[
          [FolderTree, 'Map the shape', 'Entry points, modules, and the files that matter first.'],
          [BookOpen, 'Build a mental model', 'A compact overview grounded in the repository.'],
          [MessageSquareText, 'Ask with receipts', 'Answers link back to the source paths they used.'],
        ].map(([Icon, title, copy], index) => {
          const ItemIcon = Icon as typeof FolderTree;
          return (
            <div className="rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card)/.72)] p-4" key={title as string} data-testid={`card-capability-${index}`}>
              <ItemIcon size={17} className="text-[hsl(var(--primary))]" />
              <p className="mt-5 text-[13px] font-semibold text-[hsl(var(--foreground))]">{title as string}</p>
              <p className="mt-1.5 text-[12px] leading-5 text-[hsl(var(--muted-foreground))]">{copy as string}</p>
            </div>
          );
        })}
      </div>
      <div className="mt-8 flex flex-wrap items-center gap-2">
        <span className="mr-1 font-mono text-[10px] uppercase tracking-[.15em] text-[hsl(var(--muted-foreground))]">Try a public repo</span>
        {exampleRepositories.map((repo) => (
          <button
            key={repo.url}
            className="rounded-full border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-3 py-1.5 font-mono text-[11px] text-[hsl(var(--foreground))] transition-colors hover:border-[hsl(var(--primary)/.5)] hover:text-[hsl(var(--primary))]"
            onClick={() => onExample(repo.url)}
            data-testid={`button-example-${repo.label.toLowerCase()}`}
          >
            {repo.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function AnalysisSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-20 pt-8 sm:px-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <div className="h-36 rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-6">
            <div className="skeleton-line h-3 w-28 rounded" /><div className="skeleton-line mt-5 h-6 w-2/3 rounded" /><div className="skeleton-line mt-3 h-3 w-full rounded" /><div className="skeleton-line mt-2 h-3 w-4/5 rounded" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {[1, 2].map((item) => <div className="h-64 rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5" key={item}><div className="skeleton-line h-3 w-24 rounded" /><div className="skeleton-line mt-6 h-3 w-full rounded" /><div className="skeleton-line mt-3 h-3 w-5/6 rounded" /><div className="skeleton-line mt-3 h-3 w-4/6 rounded" /></div>)}
          </div>
        </div>
        <div className="h-72 rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5"><div className="skeleton-line h-3 w-24 rounded" /><div className="skeleton-line mt-6 h-3 w-full rounded" /><div className="skeleton-line mt-3 h-3 w-5/6 rounded" /><div className="skeleton-line mt-3 h-3 w-4/6 rounded" /></div>
      </div>
    </div>
  );
}

function AnalysisView({ analysis, answer, onAsk, asking, askError }: { analysis: RepositoryAnalysis; answer: RepositoryAnswer | null; onAsk: (event: FormEvent<HTMLFormElement>) => void; asking: boolean; askError: unknown }) {
  const repoPath = useMemo(() => {
    try {
      const segments = new URL(analysis.repositoryUrl).pathname.split('/').filter(Boolean);
      return `${segments[0]}/${segments[1]}`;
    } catch { return analysis.repositoryName; }
  }, [analysis.repositoryUrl, analysis.repositoryName]);
  const [question, setQuestion] = useState('');
  const questionForm = (event: FormEvent<HTMLFormElement>) => {
    onAsk(event);
    if (question.trim()) setQuestion('');
  };
  return (
    <div className="mx-auto max-w-6xl px-4 pb-24 pt-7 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center gap-2 text-[11px] text-[hsl(var(--muted-foreground))]">
        <span className="font-mono text-[hsl(var(--primary))]">analysis</span><ChevronRight size={13} /><span className="font-mono">{repoPath}</span>
        <span className="ml-auto font-mono text-[10px]">indexed {formatDate(analysis.analyzedAt)}</span>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <main className="min-w-0 space-y-5">
          <section className="repolens-rise rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 shadow-[0_10px_35px_hsl(222_30%_20%/.045)] sm:p-7" data-testid="panel-overview">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Github size={18} className="text-[hsl(var(--foreground))]" />
                  <h1 className="text-2xl font-semibold tracking-[-.035em]">{analysis.repositoryName}</h1>
                </div>
                <a href={analysis.repositoryUrl} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1.5 font-mono text-[11px] text-[hsl(var(--muted-foreground))] transition-colors hover:text-[hsl(var(--primary))]" data-testid="link-repository">
                  {analysis.repositoryUrl.replace(/^https?:\/\//, '')}<ExternalLink size={11} />
                </a>
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-2.5 py-1.5">
                <CircleDot size={13} className="text-[hsl(var(--primary))]" /><span className="font-mono text-[11px] text-[hsl(var(--muted-foreground))]">{analysis.language}</span>
              </div>
            </div>
            <p className="mt-7 max-w-3xl text-[14px] leading-7 text-[hsl(var(--foreground)/.82)]">{analysis.overview}</p>
            <div className="mt-6 flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-md bg-[hsl(var(--accent))] px-2.5 py-1.5 font-mono text-[11px] text-[hsl(var(--accent-foreground))]"><Star size={12} fill="currentColor" /> {analysis.stars.toLocaleString()} stars</span>
              <span className="inline-flex items-center gap-1.5 rounded-md bg-[hsl(var(--muted))] px-2.5 py-1.5 font-mono text-[11px] text-[hsl(var(--muted-foreground))]"><Check size={12} /> repository mapped</span>
            </div>
          </section>
          <div className="grid gap-5 md:grid-cols-2">
            <section className="repolens-rise repolens-rise-delay-1 rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5" data-testid="panel-entry-points">
              <div className="mb-3 flex items-center justify-between"><h2 className="flex items-center gap-2 text-[13px] font-semibold"><Terminal size={15} className="text-[hsl(var(--primary))]" /> Entry points</h2><span className="font-mono text-[10px] text-[hsl(var(--muted-foreground))]">{analysis.entryPoints.length} paths</span></div>
              {analysis.entryPoints.map((file, index) => <FileRow {...file} index={`entry-${index}`.length + index} key={file.path} />)}
            </section>
            <section className="repolens-rise repolens-rise-delay-2 rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5" data-testid="panel-key-files">
              <div className="mb-3 flex items-center justify-between"><h2 className="flex items-center gap-2 text-[13px] font-semibold"><Code2 size={15} className="text-[hsl(var(--primary))]" /> Key files</h2><span className="font-mono text-[10px] text-[hsl(var(--muted-foreground))]">{analysis.keyFiles.length} paths</span></div>
              {analysis.keyFiles.map((file, index) => <FileRow {...file} index={`key-${index}`.length + index + 20} key={file.path} />)}
            </section>
          </div>
          <section className="repolens-rise repolens-rise-delay-3 rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 sm:p-6" data-testid="panel-architecture">
            <div className="mb-5 flex items-center gap-2"><Network size={15} className="text-[hsl(var(--primary))]" /><h2 className="text-[13px] font-semibold">Architecture notes</h2></div>
            <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
              {analysis.architecture.map((item, index) => <div className="flex gap-3 text-[13px] leading-6 text-[hsl(var(--foreground)/.78)]" key={item} data-testid={`text-architecture-${index}`}><span className="mt-2 size-1.5 shrink-0 rounded-full bg-[hsl(var(--primary))]" />{item}</div>)}
            </div>
          </section>
        </main>
        <aside className="lg:sticky lg:top-6">
          <section className="rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 shadow-[0_10px_35px_hsl(222_30%_20%/.045)]" data-testid="panel-ask">
            <div className="flex items-start gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-[hsl(var(--primary)/.1)] text-[hsl(var(--primary))]"><Sparkles size={16} /></div>
              <div><h2 className="text-[13px] font-semibold">Ask this repository</h2><p className="mt-1 text-[11px] leading-5 text-[hsl(var(--muted-foreground))]">Questions stay scoped to the code you just mapped.</p></div>
            </div>
            <form onSubmit={questionForm} className="mt-5">
              <textarea name="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Where does request validation happen?" className="min-h-[98px] w-full resize-none rounded-xl border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 py-2.5 text-[12px] leading-5 outline-none transition-colors placeholder:text-[hsl(var(--muted-foreground)/.7)] focus:border-[hsl(var(--primary))] focus:ring-2 focus:ring-[hsl(var(--primary)/.12)]" data-testid="input-question" />
              <button type="submit" disabled={!question.trim() || asking} className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-[hsl(var(--primary))] px-3 py-2.5 text-[12px] font-semibold text-[hsl(var(--primary-foreground))] transition-all hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-45" data-testid="button-ask">
                {asking ? <><LoaderCircle size={14} className="animate-spin" /> Tracing the code</> : <><Search size={14} /> Ask question</>}
              </button>
            </form>
            {Boolean(askError) && <div className="mt-4 flex gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-[11px] leading-5 text-red-800" data-testid="status-ask-error"><CircleAlert size={14} className="mt-0.5 shrink-0" />{errorMessage(askError)}</div>}
            {answer && <div className="mt-5 border-t border-[hsl(var(--border))] pt-5 repolens-rise" data-testid="panel-answer">
              <p className="whitespace-pre-line text-[12px] leading-6 text-[hsl(var(--foreground)/.84)]">{answer.answer}</p>
              <div className="mt-5"><div className="mb-2 flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[.14em] text-[hsl(var(--muted-foreground))]"><BookOpen size={11} /> Sources</div>
                <div className="space-y-1.5">{answer.sources.map((source, index) => <div className="flex items-start gap-2 rounded-md bg-[hsl(var(--muted)/.65)] px-2.5 py-2 font-mono text-[10px] text-[hsl(var(--muted-foreground))]" key={source} data-testid={`text-source-${index}`}><span className="text-[hsl(var(--primary))]">0{index + 1}</span><span className="break-all">{source}</span></div>)}</div>
              </div>
            </div>}
          </section>
          <div className="mt-4 flex items-start gap-2 px-1 text-[10px] leading-5 text-[hsl(var(--muted-foreground))]"><Globe2 size={13} className="mt-0.5 shrink-0" /> Answers are generated from a structured snapshot of this public repository.</div>
        </aside>
      </div>
    </div>
  );
}

function Home() {
  const [repositoryUrl, setRepositoryUrl] = useState('');
  const [analysis, setAnalysis] = useState<RepositoryAnalysis | null>(null);
  const [answer, setAnswer] = useState<RepositoryAnswer | null>(null);
  const [validationError, setValidationError] = useState('');
  const analyze = useAnalyzeRepository();
  const ask = useAskRepository();

  const submitAnalysis = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const url = repositoryUrl.trim();
    if (!isGithubUrl(url)) {
      setValidationError('Enter a public GitHub URL in the form github.com/owner/repository.');
      return;
    }
    setValidationError('');
    setAnswer(null);
    analyze.mutate({ data: { repositoryUrl: url } }, { onSuccess: (result) => setAnalysis(result) });
  };

  const submitQuestion = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const question = new FormData(form).get('question')?.toString().trim() ?? '';
    if (!question || !analysis) return;
    ask.mutate({ data: { repositoryUrl: analysis.repositoryUrl, question } }, { onSuccess: (result) => setAnswer(result) });
  };

  const reset = () => {
    setAnalysis(null);
    setAnswer(null);
    setValidationError('');
  };

  return (
    <div className="noise-layer min-h-[100dvh] bg-transparent">
      <header className="border-b border-[hsl(var(--border)/.75)] bg-[hsl(var(--background)/.86)] backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
          <button onClick={reset} className="flex items-center gap-2.5" data-testid="button-brand">
            <span className="flex size-7 items-center justify-center rounded-lg bg-[hsl(var(--sidebar))] text-[hsl(var(--sidebar-primary))]"><Search size={14} strokeWidth={2.5} /></span>
            <span className="text-[13px] font-bold tracking-[-.02em]">Repo<span className="text-[hsl(var(--primary))]">Lens</span></span>
          </button>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-1.5 font-mono text-[10px] text-[hsl(var(--muted-foreground))] sm:flex"><span className="size-1.5 rounded-full bg-[hsl(var(--primary))]" /> public repositories</span>
            <a href="https://github.com" target="_blank" rel="noreferrer" className="rounded-md p-1.5 text-[hsl(var(--muted-foreground))] transition-colors hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]" data-testid="link-github"><Github size={16} /></a>
          </div>
        </div>
      </header>
      <div className="border-b border-[hsl(var(--border)/.65)] bg-[hsl(var(--card)/.45)]">
        <form onSubmit={submitAnalysis} className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:px-6">
          <div className="relative min-w-0 flex-1">
            <Github size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
            <input value={repositoryUrl} onChange={(event) => { setRepositoryUrl(event.target.value); if (validationError) setValidationError(''); }} placeholder="Paste a public GitHub repository URL" className={`h-10 w-full rounded-lg border bg-[hsl(var(--background))] pl-9 pr-3 font-mono text-[12px] outline-none transition-all placeholder:text-[hsl(var(--muted-foreground)/.8)] focus:ring-2 focus:ring-[hsl(var(--primary)/.12)] ${validationError ? 'border-red-400 focus:border-red-500' : 'border-[hsl(var(--input))] focus:border-[hsl(var(--primary))]'}`} data-testid="input-repository-url" />
          </div>
          <button type="submit" disabled={analyze.isPending} className="flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg bg-[hsl(var(--sidebar))] px-4 text-[12px] font-semibold text-[hsl(var(--sidebar-foreground))] transition-all hover:bg-[hsl(var(--sidebar-accent))] disabled:cursor-wait disabled:opacity-70" data-testid="button-analyze">
            {analyze.isPending ? <><LoaderCircle size={14} className="animate-spin" /> Mapping repository</> : <><ArrowUpRight size={14} /> Analyze repository</>}
          </button>
        </form>
        {validationError && <div className="mx-auto flex max-w-6xl items-center gap-1.5 px-4 pb-3 text-[11px] text-red-700 sm:px-6" data-testid="status-invalid-url"><CircleAlert size={13} />{validationError}</div>}
      </div>
      {analyze.isError && !analyze.isPending && <div className="mx-auto mt-6 flex max-w-6xl items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[12px] text-red-800 sm:px-6" data-testid="status-analysis-error"><span className="flex items-center gap-2"><CircleAlert size={15} />{errorMessage(analyze.error)}</span><button className="font-semibold underline underline-offset-2" onClick={submitAnalysis as unknown as () => void} data-testid="button-retry-analysis">Retry</button></div>}
      {analyze.isPending ? <AnalysisSkeleton /> : analysis ? <AnalysisView analysis={analysis} answer={answer} onAsk={submitQuestion} asking={ask.isPending} askError={ask.error} /> : <EmptyState onExample={setRepositoryUrl} />}
      <footer className="mx-auto flex max-w-6xl items-center justify-between border-t border-[hsl(var(--border)/.55)] px-4 py-5 font-mono text-[9px] uppercase tracking-[.12em] text-[hsl(var(--muted-foreground))] sm:px-6"><span>RepoLens / focused code reading</span><span>v0.1</span></footer>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <Home />
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

export default App;
