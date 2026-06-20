// ════════════════════════════════════════════════════════════
// quiz-renderer.js — renderQuestion + renderOptions
// Depende de variables globales declaradas en display.html:
//   currentQId, _lastOptionsKey, adjustTextSize, typewriteText, esc
// ════════════════════════════════════════════════════════════

const CAT_NAMES = {
  quiensoy:   '🎭 ¿Quién Soy?',
  libros:     '📜 Libros de la Biblia',
  versiculos: '✨ Versículos',
};

const CAT_COLORS = {
  quiensoy:   '#800020',
  libros:     '#1a3a5c',
  versiculos: '#b8860b',
};

// ────────────────────────────────────────────────────────────
// renderOptions
//   p                – objeto pregunta
//   mostrarOpc       – bool: ¿mostrar las opciones?
//   mostrarResp      – bool: ¿revelar la respuesta correcta?
//   opcionSeleccionada – índice seleccionado por el equipo (o null)
// ────────────────────────────────────────────────────────────
function renderOptions(p, mostrarOpc, mostrarResp, opcionSeleccionada) {
  const container = document.getElementById('optionsContainer');
  const scores    = document.getElementById('scoresZone');

  if (!container) return;

  // Ocultar si no hay opciones que mostrar
  if (!mostrarOpc || !p || !p.opciones || p.opciones.length === 0) {
    container.innerHTML = '';
    container.classList.remove('show');
    _lastOptionsKey = '';
    if (scores) scores.classList.remove('scores-compact');
    return;
  }

  container.style.display = '';
  if (scores) scores.classList.add('scores-compact');

  const key         = JSON.stringify(p.opciones);
  const sameContent = (key === _lastOptionsKey);
  _lastOptionsKey   = key;

  function applyBaseCardStyles(card) {
    card.style.setProperty('display', 'flex');
    card.style.setProperty('align-items', 'center');
    card.style.setProperty('gap', '20px');
    card.style.setProperty('padding', '30px 36px');
    card.style.setProperty('border-radius', '16px');
    card.style.setProperty('font-size', '26px');
    card.style.setProperty('font-weight', '800');
    card.style.setProperty(
      'transition',
      'all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)'
    );
    card.style.setProperty('border', '2px solid #2e2e2e');
    card.style.setProperty('background', '#ffffff', 'important');
    card.style.setProperty('color', '#000000', 'important');
    card.style.setProperty('transform', 'scale(1)', 'important');
    card.style.setProperty('box-shadow', 'none', 'important');
    card.style.setProperty('opacity', '1', 'important');
    card.style.setProperty('text-shadow', 'none');
    card.style.setProperty('filter', 'none', 'important');
  }

  function applySelectedPreview(card) {
    card.style.setProperty('background', 'linear-gradient(135deg, #B45309 0%, #D97706 100%)', 'important');
    card.style.setProperty('border-color', '#FBBF24', 'important');
    card.style.setProperty('color', '#ffffff', 'important');
    card.style.setProperty('transform', 'scale(1.02)', 'important');
    card.style.setProperty('box-shadow', '0 0 25px rgba(217, 119, 6, 0.5)', 'important');
    card.style.setProperty('opacity', '1', 'important');
  }

  function applyCorrectReveal(card) {
    card.style.setProperty('background', 'linear-gradient(135deg, #059669 0%, #10B981 100%)', 'important');
    card.style.setProperty('border-color', '#34D399', 'important');
    card.style.setProperty('color', '#ffffff', 'important');
    card.style.setProperty('transform', 'scale(1.04)', 'important');
    card.style.setProperty('box-shadow', '0 0 30px rgba(16, 185, 129, 0.6), inset 0 0 15px rgba(255, 255, 255, 0.2)', 'important');
    card.style.setProperty('text-shadow', '0 2px 4px rgba(0, 0, 0, 0.3)');
    card.style.setProperty('opacity', '1', 'important');
    card.style.setProperty('filter', 'none', 'important');
  }

  function applyWrongReveal(card) {
    card.style.setProperty('background', 'linear-gradient(135deg, #991B1B 0%, #DC2626 100%)', 'important');
    card.style.setProperty('border-color', '#F87171', 'important');
    card.style.setProperty('color', 'rgba(255, 255, 255, 0.85)', 'important');
    card.style.setProperty('transform', 'scale(0.97)', 'important');
    card.style.setProperty('box-shadow', '0 0 15px rgba(220, 38, 38, 0.2)', 'important');
    card.style.setProperty('opacity', '0.75', 'important');
    card.style.setProperty('text-shadow', 'none');
    card.style.setProperty('filter', 'none', 'important');
  }

  if (!sameContent) {
    // ── Construir tarjetas desde cero ──
    container.innerHTML = '';
    const labels = ['A', 'B', 'C'];

    p.opciones.forEach((opcion, index) => {
      const card = document.createElement('div');
      card.className = 'option-card';
      card.id = `opcion-box-${index}`;
      applyBaseCardStyles(card);

      // Delay escalonado de entrada (no aplica si ya se reveló)
      card.style.transitionDelay = mostrarResp ? '0ms' : `${index * 150}ms`;

      // Estados de respuesta / selección
      if (mostrarResp) {
        card.classList.add('answered');
        if (index === p.respuesta_correcta) {
          card.classList.add('correct');
          applyCorrectReveal(card);
        } else {
          card.classList.add('wrong');
          applyWrongReveal(card);
        }
      } else if (opcionSeleccionada !== null && opcionSeleccionada !== undefined && index === opcionSeleccionada) {
        if (index === p.respuesta_correcta) {
          card.classList.add('correct');
          applyCorrectReveal(card);
        } else {
          card.classList.add('wrong');
          applyWrongReveal(card);
        }
      }

      // Color de categoría en el borde (si la pregunta tiene categoría)
      const catColor = CAT_COLORS[p.categoria];
      if (catColor && !mostrarResp) {
        card.style.borderColor = catColor;
      }

      // ── Elementos internos ──
      const letraDiv = document.createElement('div');
      letraDiv.className   = 'opt-letter';
      letraDiv.textContent = labels[index];

      const textoDiv = document.createElement('div');
      textoDiv.className   = 'opt-text';
      textoDiv.textContent = opcion;
      if (typeof window.adjustOptTextSize === 'function') {
        window.adjustOptTextSize(textoDiv, opcion);
      }

      card.appendChild(letraDiv);
      card.appendChild(textoDiv);

      // Indicador ✓ / ✕ (solo al revelar respuesta)
      if (mostrarResp) {
        const checkDiv = document.createElement('div');
        checkDiv.className   = 'opt-check';
        checkDiv.textContent = index === p.respuesta_correcta ? '✓' : '✕';
        card.appendChild(checkDiv);
      }

      container.appendChild(card);
    });

    // Forzar reflow y activar animación de entrada
    requestAnimationFrame(() => {
      container.classList.add('show');
      container.querySelectorAll('.option-card').forEach(el => el.classList.add('show'));
    });

  } else if (mostrarResp && container.classList.contains('show')) {
    // ── Misma pregunta, revelar respuesta sobre tarjetas existentes ──
    container.querySelectorAll('.option-card').forEach((el, i) => {
      applyBaseCardStyles(el);
      el.classList.add('answered');
      el.classList.remove('correct', 'wrong', 'selected');
      el.removeAttribute('data-selected');
      el.style.transitionDelay = '0ms';
      // Restaurar borde neutro al revelar
      el.style.borderColor = '';

      if (i === p.respuesta_correcta) {
        el.classList.add('correct');
        applyCorrectReveal(el);
        // Añadir check si no existe aún
        if (!el.querySelector('.opt-check')) {
          const checkDiv = document.createElement('div');
          checkDiv.className   = 'opt-check';
          checkDiv.textContent = '✓';
          el.appendChild(checkDiv);
        }
      } else {
        el.classList.add('wrong');
        applyWrongReveal(el);
        if (!el.querySelector('.opt-check')) {
          const checkDiv = document.createElement('div');
          checkDiv.className   = 'opt-check';
          checkDiv.textContent = '✕';
          el.appendChild(checkDiv);
        }
      }
    });

  } else if (!mostrarResp) {
    // ── Misma pregunta, actualizar selección con feedback instantáneo ──
    container.querySelectorAll('.option-card').forEach((el, i) => {
      el.classList.remove('selected', 'correct', 'wrong');
      el.removeAttribute('data-selected');
      el.style.removeProperty('opacity');
      el.style.removeProperty('filter');
      applyBaseCardStyles(el);
      if (opcionSeleccionada !== null && opcionSeleccionada !== undefined && i === opcionSeleccionada) {
        if (i === p.respuesta_correcta) {
          el.classList.add('correct');
          applyCorrectReveal(el);
        } else {
          el.classList.add('wrong');
          applyWrongReveal(el);
        }
      }
    });
  }
}

// ────────────────────────────────────────────────────────────
// renderQuestion
//   p                – objeto pregunta (null = sin pregunta)
//   mostrarResp      – bool
//   mostrarOpc       – bool
//   opcionSeleccionada – índice o null
// ────────────────────────────────────────────────────────────
function renderQuestion(p, mostrarResp, mostrarOpc, opcionSeleccionada) {
  const qText      = document.getElementById('qText');
  const qEye       = document.getElementById('qEyebrow');
  const qCatBadge  = document.getElementById('qCatBadge');
  const ansBlock   = document.getElementById('ansBlock');
  const ansText    = document.getElementById('ansText');

  const attachedIds = ['atTL','atTR','atBL','atBR','atUnder','atOver','atDotL','atDotR'];

  function showAttached(show) {
    attachedIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.toggle('show', show);
    });
  }

  if (p && p.id) {
    // ── Badge de categoría ──
    if (p.categoria && CAT_NAMES[p.categoria]) {
      qCatBadge.textContent        = CAT_NAMES[p.categoria];
      qCatBadge.style.background   = CAT_COLORS[p.categoria] || '#800020';
      qCatBadge.style.display      = '';
      qText.setAttribute('data-category', p.categoria);
      qEye.textContent             = CAT_NAMES[p.categoria];
      qEye.setAttribute('data-category', p.categoria);
    } else if (p.category && CAT_NAMES[p.category]) {
      // compatibilidad con campo 'category' (inglés)
      qCatBadge.textContent        = CAT_NAMES[p.category];
      qCatBadge.style.background   = CAT_COLORS[p.category] || '#800020';
      qCatBadge.style.display      = '';
      qText.setAttribute('data-category', p.category);
      qEye.textContent             = CAT_NAMES[p.category];
      qEye.setAttribute('data-category', p.category);
    } else {
      qCatBadge.style.display = 'none';
      qEye.textContent        = 'Pregunta';
      qEye.removeAttribute('data-category');
    }

    if (p.id !== currentQId) {
      // ── Pregunta nueva: animar transición ──
      currentQId = p.id;
      qText.classList.remove('visible');
      qEye.classList.remove('visible');
      ansBlock.classList.remove('visible');
      showAttached(false);

      const optCont = document.getElementById('optionsContainer');
      optCont.innerHTML = '';
      optCont.classList.remove('show');
      _lastOptionsKey = '';

      setTimeout(() => {
        qText.classList.remove('empty');
        qText.textContent = p.texto;
        adjustTextSize(qText, p.texto);
        void qText.offsetWidth;
        if (typeof window._beforeQuestionVisible === 'function') {
          window._beforeQuestionVisible(qText);
        }
        qText.classList.add('visible');
        qEye.classList.add('visible');
        showAttached(true);
        renderOptions(p, mostrarOpc, mostrarResp, opcionSeleccionada);
      }, 360);

    } else {
      // ── Misma pregunta: actualizar opciones / respuesta ──
      renderOptions(p, mostrarOpc, mostrarResp, opcionSeleccionada);
    }

    // ── Bloque de respuesta ──
    const resp = p.respuesta || '';
    adjustTextSize(ansText, resp);
    if (mostrarResp && resp) {
      if (!ansBlock.classList.contains('visible')) {
        ansBlock.classList.add('visible');
        setTimeout(() => typewriteText(ansText, resp, 300), 100);
      } else {
        ansText.textContent = resp;
      }
    } else {
      ansBlock.classList.remove('visible');
      ansText.textContent = '';
    }

  } else {
    // ── Sin pregunta activa ──
    if (currentQId !== null) {
      currentQId = null;
      qText.classList.remove('visible');
      qEye.classList.remove('visible');
      ansBlock.classList.remove('visible');
      showAttached(false);

      const optCont = document.getElementById('optionsContainer');
      optCont.innerHTML = '';
      optCont.classList.remove('show');
      document.getElementById('scoresZone')?.classList.remove('scores-compact');

      setTimeout(() => {
        qText.classList.add('empty');
        qText.textContent = 'Esperando pregunta…';
        adjustTextSize(qText, 'Esperando pregunta…');
        void qText.offsetWidth;
        if (typeof window._beforeQuestionVisible === 'function') {
          window._beforeQuestionVisible(qText);
        }
        qText.classList.add('visible');
      }, 380);
    }
  }
}
