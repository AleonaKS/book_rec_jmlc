document.addEventListener('DOMContentLoaded', function() {
    // Инициализация звезд рейтинга
    function initializeStars() {
        document.querySelectorAll('.score-stars.editable').forEach(starsContainer => {
            const stars = starsContainer.querySelectorAll('.star');
            const score = parseInt(starsContainer.dataset.score) || 0;
            const hiddenInput = starsContainer.nextElementSibling;
            
            stars.forEach(star => {
                const starValue = parseInt(star.dataset.value);
                star.classList.toggle('filled', starValue <= score);
                star.textContent = starValue <= score ? '★' : '☆';
            });
            
            if (hiddenInput && hiddenInput.type === 'hidden') {
                hiddenInput.value = score;
            }
        });
    }
    
    initializeStars();

    // Обработчики для звездочек
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('star')) {
            const star = e.target;
            const starsContainer = star.closest('.score-stars');
            const stars = starsContainer.querySelectorAll('.star');
            const clickedValue = parseInt(star.dataset.value);
            const hiddenInput = starsContainer.nextElementSibling;
            
            starsContainer.dataset.score = clickedValue;
            stars.forEach(s => {
                const sValue = parseInt(s.dataset.value);
                s.classList.toggle('filled', sValue <= clickedValue);
                s.textContent = sValue <= clickedValue ? '★' : '☆';
            });
            
            if (hiddenInput && hiddenInput.type === 'hidden') {
                hiddenInput.value = clickedValue;
            }
        } 
    });

    // Обработчики для раскрывающихся блоков
    document.querySelectorAll('.toggle-button').forEach(btn => {
        btn.addEventListener('click', () => {
            const content = document.getElementById(btn.getAttribute('aria-controls'));
            if (content) {
                const isOpen = content.classList.toggle('open');
                btn.setAttribute('aria-expanded', isOpen);
                btn.querySelector('.arrow').textContent = isOpen ? '▲' : '▼';
            }
        });
    });

    // Поиск в блоках предпочтений
    document.querySelectorAll('.search-input').forEach(input => {
        const container = document.getElementById(input.dataset.target);
        if (container) {
            input.addEventListener('input', () => {
                const filter = input.value.toLowerCase();
                container.querySelectorAll('label').forEach(label => {
                    const text = label.getAttribute('data-name');
                    label.style.display = text.includes(filter) ? '' : 'none';
                });
            });
        }
    });

    // Обновление конфликтов
    function updateConflicts() {
        const selectedFavGenres = new Set(
            Array.from(document.querySelectorAll('#favoriteGenresCheckboxes input[type="checkbox"]:checked'))
                .map(el => el.value)
        );
        const selectedDislikedGenres = new Set(
            Array.from(document.querySelectorAll('#dislikedGenresCheckboxes input[type="checkbox"]:checked'))
                .map(el => el.value)
        );
        
        document.querySelectorAll('#favoriteGenresCheckboxes input[type="checkbox"]').forEach(checkbox => {
            if (selectedDislikedGenres.has(checkbox.value)) {
                checkbox.disabled = true;
                checkbox.closest('label').style.opacity = '0.5';
            } else {
                checkbox.disabled = false;
                checkbox.closest('label').style.opacity = '1';
            }
        });
        
        document.querySelectorAll('#dislikedGenresCheckboxes input[type="checkbox"]').forEach(checkbox => {
            if (selectedFavGenres.has(checkbox.value)) {
                checkbox.disabled = true;
                checkbox.closest('label').style.opacity = '0.5';
            } else {
                checkbox.disabled = false;
                checkbox.closest('label').style.opacity = '1';
            }
        });
        
        const selectedFavTags = new Set(
            Array.from(document.querySelectorAll('#favoriteTagsCheckboxes input[type="checkbox"]:checked'))
                .map(el => el.value)
        );
        const selectedDislikedTags = new Set(
            Array.from(document.querySelectorAll('#dislikedTagsCheckboxes input[type="checkbox"]:checked'))
                .map(el => el.value)
        );
        
        document.querySelectorAll('#favoriteTagsCheckboxes input[type="checkbox"]').forEach(checkbox => {
            if (selectedDislikedTags.has(checkbox.value)) {
                checkbox.disabled = true;
                checkbox.closest('label').style.opacity = '0.5';
            } else {
                checkbox.disabled = false;
                checkbox.closest('label').style.opacity = '1';
            }
        });
        
        document.querySelectorAll('#dislikedTagsCheckboxes input[type="checkbox"]').forEach(checkbox => {
            if (selectedFavTags.has(checkbox.value)) {
                checkbox.disabled = true;
                checkbox.closest('label').style.opacity = '0.5';
            } else {
                checkbox.disabled = false;
                checkbox.closest('label').style.opacity = '1';
            }
        });
    }

    updateConflicts();
    document.querySelectorAll('.checkbox-multi-col input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', updateConflicts);
    });
});