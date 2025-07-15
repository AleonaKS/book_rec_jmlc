document.querySelectorAll('.stars').forEach(starsDiv => {
  starsDiv.addEventListener('click', function(e) {
    if (!e.target.classList.contains('star')) return;
    let val = parseInt(e.target.dataset.value);
    let li = e.target.closest('li');
    let input = li.querySelector('input[type=hidden]');
    input.value = val;

    // Обновляем визуал
    starsDiv.querySelectorAll('.star').forEach(star => {
      let starVal = parseInt(star.dataset.value);
      star.classList.toggle('filled', starVal <= val);
    });
  });
});


function initializeStars() {
  document.querySelectorAll('.score-stars.editable').forEach(starsContainer => {
    const stars = starsContainer.querySelectorAll('.star');
    const score = parseInt(starsContainer.dataset.score) || 0;
    const hiddenInput = starsContainer.nextElementSibling;
    // Устанавливаем начальное состояние звезд
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
  // Инициализация при загрузке
  initializeStars();

  // Обработчики для  звездочек
  document.addEventListener('click', function(e) {
    if (e.target.classList.contains('star')) {
        const star = e.target;
        const starsContainer = star.closest('.score-stars');
        const stars = starsContainer.querySelectorAll('.star');
        const clickedValue = parseInt(star.dataset.value);
        const hiddenInput = starsContainer.nextElementSibling;
        // Обновляем оценку
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

  // Обработчики - раскрывающийся блок и поиск  
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

  // Инициализация блоков предпочтений
  function initPreferenceBlock(blockId, checkboxesId, scoreInputName, itemType) {
    const container = document.getElementById(checkboxesId);
    const selectedList = document.getElementById(blockId + '_selected_list');

    if (!container || !selectedList) return;

    // Функция создания элемента списка
    function createListItem(id, name, initialScore = 0) {
      const li = document.createElement('li');
      li.dataset.itemId = id;
      li.dataset.itemType = itemType;
 
      li.appendChild(document.createTextNode(name + ' '));
 
      const scoreSpan = document.createElement('span');
      scoreSpan.className = 'score-stars editable';
      scoreSpan.title = 'Нажмите, чтобы изменить оценку';
      scoreSpan.dataset.score = initialScore;

      for (let i = 1; i <= 5; i++) {
        const star = document.createElement('span');
        star.className = 'star';
        star.dataset.value = i;
        star.textContent = i <= initialScore ? '★' : '☆';
        if (i <= initialScore) star.classList.add('filled');
        scoreSpan.appendChild(star);
      }
      li.appendChild(scoreSpan);
 
      const hiddenInput = document.createElement('input');
      hiddenInput.type = 'hidden';
      hiddenInput.name = `${scoreInputName}_${id}`;
      hiddenInput.value = initialScore;
      li.appendChild(hiddenInput);

      return li;
    }

    // Обработчик изменения чекбоксов
    container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
      checkbox.addEventListener('change', function() {
        const id = this.value;
        const name = this.closest('label').textContent.trim();
        const selectedList = document.getElementById(blockId + '_selected_list');

        if (this.checked) { 
          const li = createListItem(id, name, 0);
          selectedList.appendChild(li);
           
          const noItemsMsg = selectedList.querySelector('li:not([data-item-id])');
          if (noItemsMsg) noItemsMsg.remove();
        } else { 
          const itemToRemove = selectedList.querySelector(`li[data-item-id="${id}"]`);
          if (itemToRemove) itemToRemove.remove(); 
          if (selectedList.children.length === 0) {
            const noItemsMsg = document.createElement('li');
            noItemsMsg.textContent = `Нет выбранных ${blockId.replace('Block', '').toLowerCase()}`;
            selectedList.appendChild(noItemsMsg);
          }
        }
      });
    });
  }

  // Инициализация всех блоков
  initPreferenceBlock('favoriteAuthorsBlock', 'favoriteAuthorsCheckboxes', 'favoriteauthors_score', 'favoriteauthors');
  initPreferenceBlock('favoriteGenresBlock', 'favoriteGenresCheckboxes', 'favoritegenres_score', 'favoritegenres');
  initPreferenceBlock('favoriteTagsBlock', 'favoriteTagsCheckboxes', 'favoritetags_score', 'favoritetags');
  initPreferenceBlock('dislikedGenresBlock', 'dislikedGenresCheckboxes', 'dislikedgenres_score', 'dislikedgenres');
  initPreferenceBlock('dislikedTagsBlock', 'dislikedTagsCheckboxes', 'dislikedtags_score', 'dislikedtags');
 
document.querySelectorAll('.score-stars input[type="radio"]').forEach(radio => {
    radio.addEventListener('change', function() { });
});


function updateConflicts() {
  // Получаем все выбранные элементы
  const selectedFavGenres = new Set(
    Array.from(document.querySelectorAll('#favoriteGenresCheckboxes input[type="checkbox"]:checked'))
      .map(el => el.value)
  );
  const selectedDislikedGenres = new Set(
    Array.from(document.querySelectorAll('#dislikedGenresCheckboxes input[type="checkbox"]:checked'))
      .map(el => el.value)
  );
  
  // Блокируем выбор в противоположных списках
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
  
  // аналогично для тегов
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

// Вызываем при загрузке и при любом изменении чекбоксов
document.addEventListener('DOMContentLoaded', () => {
  updateConflicts();
  document.querySelectorAll('.checkbox-multi-col input[type="checkbox"]').forEach(checkbox => {
    checkbox.addEventListener('change', updateConflicts);
  });
}); 