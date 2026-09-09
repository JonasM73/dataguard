/**
 * Le score n'est jamais montré seul : la mention rappelle qu'il résume des
 * contrôles pondérés, et un score absent s'affiche comme absent plutôt que
 * comme un zéro — un run techniquement échoué n'a pas une qualité nulle, il
 * n'a pas de qualité mesurée.
 */
export function Score({ value, size = 'md' }: { value: number | null; size?: 'sm' | 'md' | 'lg' }) {
  const classes = { sm: 'text-xl', md: 'text-3xl', lg: 'text-5xl' }[size]

  if (value === null) {
    return (
      <span className={`${classes} font-semibold text-slate-400`} title="Aucun contrôle n'a pu être exécuté">
        —
      </span>
    )
  }

  const tone = value >= 90 ? 'text-green-700' : value >= 70 ? 'text-amber-700' : 'text-red-700'
  return (
    <span className={`${classes} font-semibold tabular-nums ${tone}`}>
      {value.toFixed(value % 1 === 0 ? 0 : 2)}
      <span className="ml-0.5 text-base font-normal text-slate-500">/100</span>
    </span>
  )
}

export function Delta({ value, unit = '' }: { value: number | null; unit?: string }) {
  if (value === null || value === 0) return <span className="text-slate-500">inchangé</span>
  const positive = value > 0
  return (
    <span className={positive ? 'text-green-700' : 'text-red-700'}>
      {positive ? '+' : ''}
      {value}
      {unit}
    </span>
  )
}
