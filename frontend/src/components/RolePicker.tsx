export interface RoleOption {
  value: string;
  label: string;
}

interface RolePickerProps {
  disciplineLabel: string;
  options: RoleOption[];
  onSelect: (value: string) => void;
  onSelectAll: () => void;
}

// First-load gate, page 2 of 2: once a top-level discipline is picked
// (DisciplinePicker), narrow further to a specific role within it. For a
// discipline with several distinct fields (CS), the options are those
// fields; for a single-field discipline (finance, mechanical-engineering),
// the options are that field's own subfields instead -- either way this is
// "the roles in that field, not all roles" (see App.tsx's roleOptionsFor()).
export default function RolePicker({ disciplineLabel, options, onSelect, onSelectAll }: RolePickerProps): React.JSX.Element {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ultra-dark-mode px-6 font-raleway text-ultra-light-mode">
      <div className="w-full max-w-2xl animate-fade-up text-center">
        <h1 className="font-jost text-3xl font-semibold text-light-mode">Which role in {disciplineLabel}?</h1>
        <p className="mt-2 text-sm text-ultra-light-mode/60">
          Pick one to narrow further, or see every {disciplineLabel} role. You can change this later.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onSelect(option.value)}
              className="rounded-md border border-white/10 bg-dark-mode px-4 py-3 text-center text-light-mode
                         transition-colors hover:border-accent/50 hover:bg-dark-mode/70 focus:outline-none
                         focus:ring-2 focus:ring-accent/50"
            >
              <span className="font-medium">{option.label}</span>
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={onSelectAll}
          className="mt-6 text-sm text-ultra-light-mode/60 underline underline-offset-4 hover:text-light-mode"
        >
          See every {disciplineLabel} role
        </button>
      </div>
    </div>
  );
}
