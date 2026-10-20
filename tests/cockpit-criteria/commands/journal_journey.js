// The journey page of the criterion tests of the destination « Journal »
// (journal_destination.py). It loads the page to read in one frame, does
// the steps it is given there one after the other -- what a person does on
// the page --, and writes what the page shows at the end in the document,
// which `--dump-dom` prints:
//
//   {ok, page: {path, text, html, anchors, controls, blocks, steps}}
//
// steps     each step: {click: name} activates the first control a person
//           sees whose accessible name is `name` or starts with it;
//           {type: name, text: words} writes `words` in the field whose
//           accessible name (its label, aria-label or placeholder) is
//           `name` or starts with it, as typing does (an input event), and
//           sends its form when it is in one, as Enter does. The page is
//           read again 2.5 s after each step, or once the document a step
//           opened has loaded and settled. `steps` says, per step, whether
//           its control or field was found.
// path      the address of the document shown at the end, its query
//           included
// text      what the page shows: the text of its body as it is drawn --
//           what is hidden, or folded in a closed <details>, is not in it
// html      the source of the document shown at the end
// anchors   every element carrying data-anchor: {shown, text, content} --
//           `text` what it shows, on one line ('' when it is not drawn),
//           `content` all the text it holds, folded or not, on one line
// controls  every control a person sees: name, element, its address when
//           it is a link, disabled or not, and its aria-current,
//           aria-selected, aria-pressed and aria-expanded
// blocks    the text, on one line, of each element drawn whose own text is
//           short (under 160 characters): where a word and what is said of
//           it are looked for together
(function () {
  var query = new URLSearchParams(location.search);
  var out = document.getElementById('journey');
  var holder = document.getElementById('frames');
  var width = Number(query.get('width'));
  var height = Number(query.get('height'));
  var steps = JSON.parse(query.get('steps') || '[]');
  var SETTLE_MS = 2500;

  var CONTROLS = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [tabindex], ' +
    '[role=button], [role=link], [role=tab], [role=menuitem], [role=checkbox], [role=switch]';
  var FIELDS = 'input:not([type=hidden]):not([type=button]):not([type=submit]), textarea, [role=searchbox]';

  function line(text) { return (text || '').replace(/\s+/g, ' ').trim(); }

  function drawn(element, view) {
    if (!element.getClientRects().length) { return false; }
    var closed = element.closest('details:not([open])');
    if (closed && !element.closest('summary')) { return false; }
    var style = view.getComputedStyle(element);
    return style.visibility !== 'hidden' && style.display !== 'none';
  }

  function nameOf(element, doc) {
    var label = element.getAttribute('aria-label');
    if (label && label.trim()) { return line(label); }
    var by = element.getAttribute('aria-labelledby');
    if (by) {
      var named = line(by.split(/\s+/).map(function (id) {
        var target = doc.getElementById(id); return target ? target.textContent : '';
      }).join(' '));
      if (named) { return named; }
    }
    if (element.labels && element.labels.length) {
      var labelled = line(Array.prototype.map.call(element.labels, function (l) { return l.textContent; }).join(' '));
      if (labelled) { return labelled; }
    }
    var text = line(element.innerText || element.textContent);
    if (text && !element.matches(FIELDS)) { return text; }
    return line(element.getAttribute('placeholder') || element.getAttribute('title') || text);
  }

  function find(doc, view, selector, name) {
    var found = null;
    doc.querySelectorAll(selector).forEach(function (element) {
      var own = nameOf(element, doc);
      if (!found && drawn(element, view) && (own === name || own.indexOf(name) === 0)) { found = element; }
    });
    return found;
  }

  function read(frame) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var anchors = {}, controls = [], blocks = [];
    doc.querySelectorAll('[data-anchor]').forEach(function (element) {
      var shown = drawn(element, view);
      anchors[element.getAttribute('data-anchor')] = {
        shown: shown, text: shown ? line(element.innerText) : '', content: line(element.textContent)};
    });
    doc.querySelectorAll(CONTROLS).forEach(function (element) {
      if (!drawn(element, view)) { return; }
      controls.push({
        name: nameOf(element, doc), tag: element.tagName.toLowerCase(),
        href: element.matches('a[href]') ? element.getAttribute('href') : null,
        disabled: element.disabled === true || element.getAttribute('aria-disabled') === 'true',
        state: {current: element.getAttribute('aria-current'), selected: element.getAttribute('aria-selected'),
                pressed: element.getAttribute('aria-pressed'), expanded: element.getAttribute('aria-expanded')}});
    });
    doc.querySelectorAll('body *').forEach(function (element) {
      if (!drawn(element, view)) { return; }
      var text = line(element.innerText);
      if (text && text.length < 160) { blocks.push(text); }
    });
    return {path: view.location.pathname + view.location.search, text: doc.body ? doc.body.innerText : '',
            html: doc.documentElement.outerHTML, anchors: anchors, controls: controls, blocks: blocks};
  }

  function act(frame, step, done) {
    var doc = frame.contentDocument, view = frame.contentWindow, target;
    if (step.click !== undefined) {
      target = find(doc, view, CONTROLS, step.click);
    } else {
      target = find(doc, view, FIELDS, step.type);
    }
    if (!target) { done(false); return; }
    var finished = false;
    function settled() { if (!finished) { finished = true; done(true); } }
    frame.addEventListener('load', function () { setTimeout(settled, SETTLE_MS); }, {once: true});
    if (step.click !== undefined) {
      target.click();
    } else {
      target.focus();
      var setter = Object.getOwnPropertyDescriptor(view[target.tagName === 'TEXTAREA' ? 'HTMLTextAreaElement'
        : 'HTMLInputElement'].prototype, 'value');
      if (setter && target.matches('input, textarea')) {
        setter.set.call(target, step.text);
      } else {
        target.textContent = step.text;
      }
      target.dispatchEvent(new view.Event('input', {bubbles: true}));
      target.dispatchEvent(new view.Event('change', {bubbles: true}));
      if (target.form) {
        if (typeof target.form.requestSubmit === 'function') {
          target.form.requestSubmit();
        } else {
          target.form.submit();
        }
      }
    }
    setTimeout(function () { if (!finished && frame.contentDocument.readyState === 'complete') { settled(); } },
               SETTLE_MS);
    setTimeout(settled, SETTLE_MS * 3);
  }

  var frame = document.createElement('iframe');
  frame.style.cssText = 'border:0;display:block;width:' + width + 'px;height:' + height + 'px';
  holder.appendChild(frame);
  frame.addEventListener('load', function () {
    setTimeout(function () {
      var found = [], index = 0;
      function next() {
        if (index >= steps.length) {
          try {
            var page = read(frame);
            page.steps = found;
            out.textContent = JSON.stringify({ok: true, page: page});
          } catch (error) {
            out.textContent = JSON.stringify({ok: false, error: String(error)});
          }
          return;
        }
        act(frame, steps[index], function (was) { found.push(was); index += 1; next(); });
      }
      next();
    }, SETTLE_MS);
  }, {once: true});
  frame.src = query.get('target');
})();
