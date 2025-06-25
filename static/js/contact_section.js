var inputs = document.querySelectorAll('.js-input');

for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener('keyup', function() {
        if (this.value) {
            this.classList.add('not-empty');
        } else {
            this.classList.remove('not-empty');
        }
    });
}