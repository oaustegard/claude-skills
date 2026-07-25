/* =========================================================================
   composing-html / base.js
   Tiny vanilla helpers. No framework. Activated only if the markup needs it.
   ========================================================================= */
(function () {
  'use strict';

  // Copy-to-clipboard for <pre><code> blocks marked .code-wrap or any pre.
  function initCopyButtons() {
    document.querySelectorAll('pre').forEach(function (pre) {
      if (pre.dataset.copyInit) return;
      pre.dataset.copyInit = '1';
      var wrap = pre.parentElement;
      if (!wrap || !wrap.classList.contains('code-wrap')) {
        wrap = document.createElement('div');
        wrap.className = 'code-wrap';
        pre.parentNode.insertBefore(wrap, pre);
        wrap.appendChild(pre);
      }
      var btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.type = 'button';
      btn.textContent = 'copy';
      btn.addEventListener('click', function () {
        var text = pre.innerText;
        navigator.clipboard.writeText(text).then(function () {
          btn.textContent = 'copied';
          setTimeout(function () { btn.textContent = 'copy'; }, 1400);
        }).catch(function () { btn.textContent = 'err'; });
      });
      wrap.appendChild(btn);
    });
  }

  // Tab groups: <div class="tabgroup"><div class="tabs"><button data-target="x">..</button></div>
  //             <div class="tab-panel" data-id="x">..</div></div>
  function initTabs() {
    document.querySelectorAll('.tabgroup').forEach(function (group) {
      var buttons = group.querySelectorAll('.tabs button[data-target]');
      var panels  = group.querySelectorAll('.tab-panel[data-id]');
      function show(id) {
        buttons.forEach(function (b) { b.setAttribute('aria-selected', b.dataset.target === id ? 'true' : 'false'); });
        panels.forEach(function (p)  { p.dataset.active = p.dataset.id === id ? 'true' : 'false'; });
      }
      buttons.forEach(function (b) { b.addEventListener('click', function () { show(b.dataset.target); }); });
      var first = buttons[0];
      if (first) show(first.dataset.target);
    });
  }

  // Slide deck: arrow-key & space navigation between .slide elements.
  // Activated only when document.body has data-deck="true".
  function initDeck() {
    if (document.body.dataset.deck !== 'true') return;
    var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
    if (!slides.length) return;
    function currentIndex() {
      var mid = window.innerHeight / 2;
      for (var i = 0; i < slides.length; i++) {
        var r = slides[i].getBoundingClientRect();
        if (r.top <= mid && r.bottom > mid) return i;
      }
      return 0;
    }
    function go(delta) {
      var i = Math.max(0, Math.min(slides.length - 1, currentIndex() + delta));
      slides[i].scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    document.addEventListener('keydown', function (e) {
      if (e.target && /^(input|textarea|select)$/i.test(e.target.tagName)) return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); go(+1); }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); go(-1); }
      else if (e.key === 'Home') { e.preventDefault(); slides[0].scrollIntoView({ behavior: 'smooth' }); }
      else if (e.key === 'End')  { e.preventDefault(); slides[slides.length - 1].scrollIntoView({ behavior: 'smooth' }); }
    });
  }

  // Drag-to-reorder for editor-style triage boards.
  // Markup: a container with data-sortable="true" and direct children with [draggable="true"].
  // Cross-zone moves work because `dragged` is module-scoped, not per-zone.
  var dragged = null;

  function initSortable() {
    document.querySelectorAll('[data-sortable="true"]').forEach(function (zone) {
      if (zone.dataset.sortInit) return;
      zone.dataset.sortInit = '1';

      zone.addEventListener('dragstart', function (e) {
        var t = e.target.closest('[draggable="true"]');
        if (!t || t.parentElement !== zone) return;
        dragged = t;
        t.style.opacity = '0.4';
        try { e.dataTransfer.effectAllowed = 'move'; } catch (_) {}
      });

      zone.addEventListener('dragend', function () {
        if (dragged) dragged.style.opacity = '';
        dragged = null;
      });

      zone.addEventListener('dragover', function (e) {
        if (!dragged) return;
        e.preventDefault();
        try { e.dataTransfer.dropEffect = 'move'; } catch (_) {}
        var after = null;
        var children = Array.prototype.slice.call(zone.children)
          .filter(function (c) { return c !== dragged && c.draggable; });
        for (var i = 0; i < children.length; i++) {
          var box = children[i].getBoundingClientRect();
          if (e.clientY < box.top + box.height / 2) { after = children[i]; break; }
        }
        if (after) zone.insertBefore(dragged, after);
        else if (dragged.parentElement !== zone || zone.lastElementChild !== dragged) zone.appendChild(dragged);
      });

      zone.addEventListener('drop', function (e) {
        if (dragged) e.preventDefault();
      });
    });
  }

  // Live param controls: any [data-bind] input updates the textContent of [data-out="<name>"].
  // Optional: [data-format="number|percent|ms"].
  function initBindings() {
    var fmt = {
      number:  function (v) { return Number(v).toString(); },
      percent: function (v) { return (Number(v) * 100).toFixed(0) + '%'; },
      ms:      function (v) { return Number(v) + 'ms'; }
    };
    document.querySelectorAll('input[data-bind], select[data-bind]').forEach(function (el) {
      function push() {
        var name = el.dataset.bind;
        var f = fmt[el.dataset.format] || function (v) { return v; };
        document.querySelectorAll('[data-out="' + name + '"]').forEach(function (o) { o.textContent = f(el.value); });
        // CSS-var bridge: --bind-<name>
        document.documentElement.style.setProperty('--bind-' + name, el.value + (el.dataset.unit || ''));
      }
      el.addEventListener('input', push);
      push();
    });
  }

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    initCopyButtons();
    initTabs();
    initDeck();
    initSortable();
    initBindings();
  });
})();
