document.addEventListener('DOMContentLoaded', () => {
    // Exemplo: Fechar alertas automaticamente após 5 segundos
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.remove('show');
            alert.classList.add('fade');
        }, 5000);
    });
});