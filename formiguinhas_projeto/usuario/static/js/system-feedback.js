document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-system-feedback-toast]').forEach(function (toast) {
        var timeout;

        function fechar() {
            clearTimeout(timeout);
            toast.classList.add('toast-leaving');
            window.setTimeout(function () {
                toast.remove();
            }, 200);
        }

        function iniciarTimeout() {
            timeout = window.setTimeout(fechar, toast.getAttribute('role') === 'alert' ? 9000 : 6000);
        }

        toast.querySelector('.system-feedback-close').addEventListener('click', fechar);
        toast.addEventListener('mouseenter', function () {
            clearTimeout(timeout);
        });
        toast.addEventListener('mouseleave', iniciarTimeout);
        toast.addEventListener('focusin', function () {
            clearTimeout(timeout);
        });
        toast.addEventListener('focusout', iniciarTimeout);
        iniciarTimeout();
    });
});
