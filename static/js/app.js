// Auto-fechar toasts
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => document.querySelectorAll('.toast').forEach(t => t.remove()), 4000);
});
