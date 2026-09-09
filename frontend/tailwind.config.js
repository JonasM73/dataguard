export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Un statut n'est jamais signalé par la seule couleur : chaque badge
        // porte aussi son libellé, pour rester lisible en cas de daltonisme.
        success: '#15803d',
        warning: '#b45309',
        failed: '#b91c1c',
        skipped: '#64748b',
      },
    },
  },
  plugins: [],
}
