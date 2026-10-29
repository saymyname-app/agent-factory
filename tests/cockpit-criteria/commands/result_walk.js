// The walking page of the criterion tests of A2 (result_trial.py). It is
// the walk of B (pour_moi_walk.js) with what a judgement needs besides:
// a choice among radio buttons, an option of a list, what the page copies
// for its session, and the tabs it opens. It loads the page in one frame,
// reads it once settled, then does each step asked, one after the other,
// and reads it again after each; it writes what it read in the document,
// which `--dump-dom` prints:
//
//   {ok, start: page, steps: [{found, page, body?}]}
//
// page      path   the address the frame shows
//           text   the text of the page as shown (a closed <details>, a
//                  hidden element, is not shown)
//           controls  every visible control: its accessible name, disabled
//                  or not, a text field or not, checked or not (a radio, a
//                  box), and `holder`, the nearest data-anchor that holds it
//           folded  every <details> of the page, open or not: its summary
//                  and its whole text
//           opened  every address the page asked to open in another tab
//                  since the walk began (a link to a new tab activated,
//                  window.open), resolved against the page
//           copied  every text the page copied for the clipboard since
//                  the walk began
// step      {click: name}  the visible control whose accessible name is
//                  `name`, or starts with it, is activated
//           {fill: name, value: text}  `text` is written in the visible
//                  text field whose accessible name holds `name`
//           {check: name}  the visible radio button or box whose label
//                  holds `name` is checked, as a click on it does
//           {choose: name, option: text}  in the visible list whose
//                  accessible name holds `name`, the option whose text is
//                  `text` is selected
//           {fetch: path}  the page reads `path` of its own address; the
//                  step records the `body` read
//           wait   how long to let the page settle after the step (ms)
//           found  whether that control was there; the walk stops at the
//                  first step whose control is not
(function () {
  var query = new URLSearchParams(location.search);
  var out = document.getElementById('walk');
  var holder = document.getElementById('frames');
  var steps = JSON.parse(query.get('steps') || '[]');
  var width = Number(query.get('width'));
  var height = Number(query.get('height'));
  var SETTLE_MS = Number(query.get('settle') || 2500);
  var CONTROLS = 'a[href], button, input, select, textarea, summary, [role="button"], [role="link"], [tabindex]';
  var FIELDS = 'textarea, input:not([type]), input[type="text"], input[type="search"]';
  var CHOICES = 'input[type="radio"], input[type="checkbox"]';
  var opened = [], copied = [];

  function visible(element, view) {
    if (!element.getClientRects().length) { return false; }
    var closed = element.closest('details:not([open])');
    if (closed && !element.closest('summary')) { return false; }
    var style = view.getComputedStyle(element);
    if (style.visibility === 'hidden' || style.display === 'none') { return false; }
    var box = element.getBoundingClientRect();
    return box.width > 1 && box.height > 1;
  }

  function squash(text) { return (text || '').replace(/\s+/g, ' ').trim(); }

  function labelOf(element, doc) {
    var own = element.id ? doc.querySelector('label[for="' + element.id + '"]') : null;
    var around = own || element.closest('label');
    return around ? squash(around.innerText || around.textContent) : '';
  }

  function accessibleName(element, doc) {
    var label = element.getAttribute('aria-label');
    if (label && label.trim()) { return label.trim(); }
    var by = element.getAttribute('aria-labelledby');
    if (by) {
      var named = squash(by.split(/\s+/).map(function (id) {
        var target = doc.getElementById(id);
        return target ? (target.innerText || target.textContent || '') : '';
      }).join(' '));
      if (named) { return named; }
    }
    if (element.matches(FIELDS + ', select, ' + CHOICES)) {
      return labelOf(element, doc) || (element.getAttribute('placeholder') || element.getAttribute('title') || '').trim();
    }
    return squash(element.innerText || element.textContent) || (element.getAttribute('title') || '').trim();
  }

  // What the page opens in another tab, and what it copies, is recorded
  // here and not done: the walk stays on the page it reads.
  function watch(frame) {
    var view = frame.contentWindow, doc = frame.contentDocument;
    function record(address) {
      if (address === undefined || address === null || String(address) === '' || String(address) === 'about:blank') {
        return;
      }
      opened.push(new view.URL(String(address), view.location.href).href);
    }
    view.open = function (address) {
      record(address);
      var location = {replace: record, assign: record};
      Object.defineProperty(location, 'href', {get: function () { return ''; }, set: record});
      var tab = {closed: false, opener: null, focus: function () {}, close: function () {},
                 document: {write: function () {}, close: function () {}}};
      Object.defineProperty(tab, 'location', {get: function () { return location; }, set: record});
      return tab;
    };
    doc.addEventListener('click', function (event) {
      var link = event.target.closest && event.target.closest('a[href]');
      if (link && (link.target === '_blank' || event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        if (link.getAttribute('aria-disabled') !== 'true') { record(link.getAttribute('href')); }
      }
    }, true);
    var clipboard = {
      writeText: function (text) { copied.push(String(text)); return view.Promise.resolve(); },
      write: function () { return view.Promise.reject(new view.Error('not recorded')); }
    };
    try { Object.defineProperty(view.navigator, 'clipboard', {value: clipboard, configurable: true}); } catch (error) {}
    var execCommand = doc.execCommand.bind(doc);
    doc.execCommand = function (command) {
      if (String(command).toLowerCase() === 'copy') {
        var active = doc.activeElement;
        var selected = active && active.value !== undefined && active.selectionStart !== undefined
          ? active.value.slice(active.selectionStart, active.selectionEnd) : String(view.getSelection());
        copied.push(selected);
        return true;
      }
      return execCommand.apply(null, arguments);
    };
  }

  function read(frame) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var controls = [], folded = [];
    doc.querySelectorAll(CONTROLS).forEach(function (element) {
      if (!visible(element, view)) { return; }
      var holding = element.closest('[data-anchor]');
      controls.push({
        name: accessibleName(element, doc),
        disabled: element.disabled === true || element.getAttribute('aria-disabled') === 'true',
        field: element.matches(FIELDS),
        checked: element.matches(CHOICES) ? element.checked : null,
        holder: holding ? holding.getAttribute('data-anchor') : null
      });
    });
    doc.querySelectorAll('details').forEach(function (details) {
      var summary = details.querySelector(':scope > summary');
      folded.push({summary: summary ? squash(summary.innerText || summary.textContent) : '',
                   text: squash(details.textContent)});
    });
    return {path: view.location.pathname, text: doc.body ? doc.body.innerText : '', controls: controls,
            folded: folded, opened: opened.slice(), copied: copied.slice()};
  }

  function find(frame, step) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var selector = step.fill !== undefined ? FIELDS : step.check !== undefined ? CHOICES
                   : step.choose !== undefined ? 'select' : CONTROLS;
    var wanted = step.fill !== undefined ? step.fill : step.check !== undefined ? step.check
                 : step.choose !== undefined ? step.choose : step.click;
    var found = null;
    doc.querySelectorAll(selector).forEach(function (element) {
      if (found || !visible(element, view)) { return; }
      var name = accessibleName(element, doc);
      var matches = step.click !== undefined ? (name === wanted || name.indexOf(wanted) === 0) : name.indexOf(wanted) >= 0;
      if (matches) { found = element; }
    });
    return found;
  }

  function fill(element, value) {
    var view = element.ownerDocument.defaultView;
    var prototype = element.tagName === 'TEXTAREA' ? view.HTMLTextAreaElement.prototype : view.HTMLInputElement.prototype;
    element.focus();
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value);
    element.dispatchEvent(new view.Event('input', {bubbles: true}));
    element.dispatchEvent(new view.Event('change', {bubbles: true}));
  }

  function choose(element, text) {
    var view = element.ownerDocument.defaultView;
    var option = Array.prototype.find.call(element.options, function (o) { return squash(o.text) === text; });
    if (!option) { return false; }
    element.focus();
    element.value = option.value;
    element.dispatchEvent(new view.Event('input', {bubbles: true}));
    element.dispatchEvent(new view.Event('change', {bubbles: true}));
    return true;
  }

  var walked = {ok: true, start: null, steps: []};
  function finish() { out.textContent = JSON.stringify(walked); }

  var frame = document.createElement('iframe');
  frame.style.cssText = 'border:0;display:block;width:' + width + 'px;height:' + height + 'px';
  holder.appendChild(frame);
  frame.addEventListener('load', function () { watch(frame); });

  function next(index) {
    if (index === steps.length) { finish(); return; }
    var step = steps[index];
    if (step.fetch !== undefined) {
      frame.contentWindow.fetch(step.fetch, {credentials: 'same-origin'}).then(function (response) {
        return response.text();
      }).then(function (body) {
        walked.steps.push({found: true, body: body, page: read(frame)});
        next(index + 1);
      }, function (error) {
        walked.steps.push({found: false, body: String(error), page: read(frame)});
        finish();
      });
      return;
    }
    var target;
    try { target = find(frame, step); } catch (error) { walked.ok = false; walked.error = String(error); finish(); return; }
    var done = !!target;
    if (target) {
      if (step.fill !== undefined) { fill(target, step.value); }
      else if (step.choose !== undefined) { done = choose(target, step.option); }
      else { target.click(); }
    }
    if (!done) {
      walked.steps.push({found: false, page: read(frame)});
      finish();
      return;
    }
    setTimeout(function () {
      try {
        walked.steps.push({found: true, page: read(frame)});
      } catch (error) {
        walked.ok = false; walked.error = String(error); finish(); return;
      }
      next(index + 1);
    }, step.wait || SETTLE_MS);
  }

  frame.addEventListener('load', function () {
    setTimeout(function () {
      try { walked.start = read(frame); } catch (error) { walked.ok = false; walked.error = String(error); finish(); return; }
      next(0);
    }, SETTLE_MS);
  }, {once: true});
  frame.src = query.get('target');
})();
