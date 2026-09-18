export interface DisciplineOption {
  key: string;
  label: string;
}

interface DisciplinePickerProps {
  options: DisciplineOption[];
  onSelect: (key: string) => void;
  onSelectEverything: () => void;
}

// First-load gate, page 1 of 2: a fixed, small set of top-level disciplines
// (not the full fields.json list -- that's page 2, RolePicker, scoped to
// whichever of these gets picked here). "See everything" is a real,
// equally-first-class option (onSelectEverything) rather than an
// afterthought -- a multi-discipline viewer shouldn't have to fight the
// picker to get back to the unfiltered view.
export default function DisciplinePicker({ options, onSelect, onSelectEverything }: DisciplinePickerProps): React.JSX.Element {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ultra-dark-mode px-6 font-raleway text-ultra-light-mode">
      <div className="w-full max-w-2xl animate-fade-up text-center">
        <h1 className="font-jost text-3xl font-semibold text-light-mode">What field are you in?</h1>
        <p className="mt-2 text-sm text-ultra-light-mode/60">
          Pick one to narrow the job search to it, or see everything. You can change this later.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {options.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => onSelect(option.key)}
              className="rounded-md border border-white/10 bg-dark-mode px-4 py-6 text-center text-light-mode
                         transition-colors hover:border-accent/50 hover:bg-dark-mode/70 focus:outline-none
                         focus:ring-2 focus:ring-accent/50"
            >
              <span className="font-medium">{option.label}</span>
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={onSelectEverything}
          className="mt-6 text-sm text-ultra-light-mode/60 underline underline-offset-4 hover:text-light-mode"
        >
          See everything instead
        </button>
      </div>
    </div>
  );
}
