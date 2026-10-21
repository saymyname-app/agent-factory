// The measuring page of the criterion tests of the destination Runs
// (runs_destination.py). It loads the page to measure in one frame per
// width, reads each frame once the page has settled, then plays the steps
// asked for -- a click on a control, a wait, a reload of the page -- and
// reads the frame again after each one. It writes what it read in the
// document, which `--dump-dom` prints:
//
//   {ok, frames: [{width, readings: [reading, …]}]}
//
// A reading:
//
// href      the address the frame shows: path and query
// text      the rendered text of the page, on one line
// overflow  how far the document is wider than the frame
// anchors   every element carrying data-anchor, in the order of the page:
//           its name, its element, the anchors that hold it (nearest
//           first), whether it is drawn, its rendered text and its whole
//           text (a closed section included) on one line, whether it is
//           open (a <details>), its box in the page and the colours it is
//           drawn with (its text, its background, its left border, what
//           its ::before and ::after draw), as rgb() strings
// controls  every control drawn: its accessible name and the anchor that
//           holds it
// dialogs   the dialogs drawn (a <dialog> open, a role of dialog, a modal)
// scrolls   the boxes that scroll on their own and whose content is wider
//           than them: the anchor that holds each
// step      what the step before the reading did: `found` false when the
//           control it names is not on the page
(function () {
  var query = new URLSearchParams(location.search);
  var out = document.getElementById('measure');
  var holder = document.getElementById('frames');
  var widths = query.get('widths').split(',').map(Number);
  var height = Number(query.get('height'));
  var steps = JSON.parse(query.get('steps') || '[]');
  var SETTLE_MS = 2500;
  var CONTENT_LIMIT = 6000;
  var CONTROLS = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [tabindex], ' +
    '[role=button], [role=link], [role=tab]';

  function line(text) { return (text || '').replace(/\s+/g, ' ').trim(); }

  function drawn(element, view) {
    if (!element.getClientRects().length) { return false; }
    var closed = element.closest('details:not([open])');
    if (closed && closed !== element && !element.closest('summary')) { return false; }
    var style = view.getComputedStyle(element);
    if (style.visibility === 'hidden' || style.display === 'none') { return false; }
    var box = element.getBoundingClientRect();
    return box.width > 0.5 && box.height > 0.5;
  }

  function nameOf(element) {
    var label = element.getAttribute('aria-label');
    if (label && label.trim()) { return line(label); }
    var text = line(element.innerText || element.textContent);
    return text || line(element.getAttribute('title') || '');
  }

  function painted(value) {
    return value && value !== 'transparent' && !/rgba\([^)]*,\s*0\)$/.test(value) ? value : null;
  }

  function colours(element, view) {
    var style = view.getComputedStyle(element);
    var found = [painted(style.color), painted(style.backgroundColor)];
    if (parseFloat(style.borderLeftWidth) >= 2) { found.push(painted(style.borderLeftColor)); }
    ['::before', '::after'].forEach(function (pseudo) {
      var drawnPseudo = view.getComputedStyle(element, pseudo);
      if (drawnPseudo.content && drawnPseudo.content !== 'none') {
        found.push(painted(drawnPseudo.backgroundColor), painted(drawnPseudo.color));
      }
    });
    return found.filter(Boolean);
  }

  function anchorOf(element) {
    var holding = element.closest('[data-anchor]');
    return holding ? holding.getAttribute('data-anchor') : null;
  }

  function read(frame, width, step) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var anchors = [];
    doc.querySelectorAll('[data-anchor]').forEach(function (element) {
      var chain = [];
      for (var parent = element.parentElement; parent; parent = parent.parentElement) {
        if (parent.hasAttribute('data-anchor')) { chain.push(parent.getAttribute('data-anchor')); }
      }
      var box = element.getBoundingClientRect();
      var shown = drawn(element, view);
      anchors.push({
        name: element.getAttribute('data-anchor'), tag: element.tagName.toLowerCase(), chain: chain,
        drawn: shown, text: shown ? line(element.innerText).slice(0, CONTENT_LIMIT) : '',
        content: line(element.textContent).slice(0, CONTENT_LIMIT),
        open: element.tagName === 'DETAILS' ? element.open : null,
        box: {top: box.top + view.scrollY, bottom: box.bottom + view.scrollY, left: box.left, right: box.right},
        colours: colours(element, view)
      });
    });
    var controls = [];
    doc.querySelectorAll(CONTROLS).forEach(function (element) {
      if (drawn(element, view)) { controls.push({name: nameOf(element), anchor: anchorOf(element)}); }
    });
    var dialogs = [];
    doc.querySelectorAll('dialog[open], [role=dialog], [role=alertdialog], [aria-modal=true]').forEach(function (element) {
      if (drawn(element, view)) { dialogs.push(nameOf(element).slice(0, 80)); }
    });
    var scrolls = [];
    doc.querySelectorAll('body *').forEach(function (element) {
      if (!drawn(element, view)) { return; }
      var style = view.getComputedStyle(element);
      if (/auto|scroll/.test(style.overflowX) && element.scrollWidth > element.clientWidth + 1) {
        scrolls.push(anchorOf(element));
      }
    });
    var root = doc.documentElement;
    return {
      width: width, href: view.location.pathname + view.location.search, text: line(doc.body.innerText),
      overflow: Math.max(0, root.scrollWidth - root.clientWidth), anchors: anchors, controls: controls,
      dialogs: dialogs, scrolls: scrolls, step: step
    };
  }

  // The control drawn inside the anchor `within` (the page when none) whose
  // accessible name starts with `name`, else the first that holds it.
  function control(frame, name, within) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var scope = within ? doc.querySelector('[data-anchor="' + within + '"]') : doc;
    if (!scope) { return null; }
    var candidates = Array.prototype.filter.call(scope.querySelectorAll(CONTROLS), function (element) {
      return drawn(element, view);
    });
    return candidates.find(function (element) { return nameOf(element).indexOf(name) === 0; }) ||
      candidates.find(function (element) { return nameOf(element).indexOf(name) >= 0; }) || null;
  }

  // Play `step` in `frame`, then call `done` with what it did, once the page
  // has settled (after the load it caused, if it caused one).
  function play(frame, step, done) {
    var finished = false;
    function settle(what) {
      if (finished) { return; }
      finished = true;
      done(what);
    }
    if (step.wait) {
      setTimeout(function () { settle({wait: step.wait}); }, step.wait);
      return;
    }
    if (step.reload) {
      frame.addEventListener('load', function () { setTimeout(function () { settle({reload: true}); }, SETTLE_MS); },
                             {once: true});
      frame.contentWindow.location.reload();
      return;
    }
    var target = control(frame, step.click, step.within);
    if (!target) { settle({click: step.click, found: false}); return; }
    frame.addEventListener('load', function () {
      setTimeout(function () { settle({click: step.click, found: true}); }, SETTLE_MS);
    }, {once: true});
    target.click();
    setTimeout(function () { settle({click: step.click, found: true}); }, SETTLE_MS + 1500);
  }

  var results = new Array(widths.length), pending = widths.length;
  function finish() {
    pending -= 1;
    if (pending === 0) { out.textContent = JSON.stringify({ok: true, frames: results}); }
  }

  widths.forEach(function (width, index) {
    var frame = document.createElement('iframe');
    frame.style.cssText = 'border:0;display:block;width:' + width + 'px;height:' + height + 'px';
    holder.appendChild(frame);
    frame.addEventListener('load', function () {
      setTimeout(function () {
        var readings = [];
        function next(position, what) {
          try {
            readings.push(read(frame, width, what));
          } catch (error) {
            readings.push({width: width, href: '', text: '', overflow: 0, anchors: [], controls: [], dialogs: [],
                           scrolls: [], step: what, unread: String(error)});
          }
          if (position >= steps.length) {
            results[index] = {width: width, readings: readings};
            finish();
            return;
          }
          play(frame, steps[position], function (done) { next(position + 1, done); });
        }
        next(0, null);
      }, SETTLE_MS);
    }, {once: true});
    frame.src = query.get('target');
  });
})();
