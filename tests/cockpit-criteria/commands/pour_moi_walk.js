// The walking page of the criterion tests of B (pour_moi.py). It loads the
// page to walk in one frame, reads it once the page has settled, then does
// each step asked in it, one after the other, and reads it again after
// each; it writes what it read in the document, which `--dump-dom` prints:
//
//   {ok, start: page, steps: [{found, page}]}
//
// page      path   the address the frame shows
//           text   the text of the page as shown: what a closed <details>
//                  holds, or a hidden element, is not shown
//           controls  every visible control (link, button, field, summary,
//                  an element with a role of control or a tabindex): its
//                  accessible name, disabled or not, a text field or not,
//                  and `folds`, the summaries of the <details> that hold
//                  it, nearest first
// step      {click: name}  the visible control whose accessible name is
//                  `name`, or starts with it, is activated
//           {fill: name, value: text}  `text` is written in the visible
//                  text field whose accessible name holds `name`
//           {fetch: path}  the page reads `path` of its own address, as
//                  its scripts would; the step records the `body` read
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

  function visible(element, view) {
    if (!element.getClientRects().length) { return false; }
    var closed = element.closest('details:not([open])');
    if (closed && !element.closest('summary')) { return false; }
    var style = view.getComputedStyle(element);
    if (style.visibility === 'hidden' || style.display === 'none') { return false; }
    var box = element.getBoundingClientRect();
    return box.width > 1 && box.height > 1;
  }

  function accessibleName(element, doc) {
    var label = element.getAttribute('aria-label');
    if (label && label.trim()) { return label.trim(); }
    var by = element.getAttribute('aria-labelledby');
    if (by) {
      var named = by.split(/\s+/).map(function (id) {
        var target = doc.getElementById(id);
        return target ? (target.innerText || target.textContent || '') : '';
      }).join(' ').replace(/\s+/g, ' ').trim();
      if (named) { return named; }
    }
    if (element.matches(FIELDS + ', select')) {
      var own = element.id ? doc.querySelector('label[for="' + element.id + '"]') : null;
      var around = own || element.closest('label');
      if (around) { return (around.innerText || around.textContent || '').replace(/\s+/g, ' ').trim(); }
      return (element.getAttribute('placeholder') || element.getAttribute('title') || '').trim();
    }
    var text = (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim();
    return text || (element.getAttribute('title') || '').trim();
  }

  function folds(element) {
    var summaries = [], holder = element.parentElement;
    while (holder) {
      if (holder.tagName === 'DETAILS') {
        var summary = holder.querySelector(':scope > summary');
        summaries.push(summary ? (summary.innerText || summary.textContent || '').replace(/\s+/g, ' ').trim() : '');
      }
      holder = holder.parentElement;
    }
    return summaries;
  }

  function read(frame) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var controls = [];
    doc.querySelectorAll(CONTROLS).forEach(function (element) {
      if (!visible(element, view)) { return; }
      controls.push({
        name: accessibleName(element, doc),
        disabled: element.disabled === true || element.getAttribute('aria-disabled') === 'true',
        field: element.matches(FIELDS),
        folds: folds(element)
      });
    });
    return {path: view.location.pathname, text: doc.body ? doc.body.innerText : '', controls: controls};
  }

  function find(frame, step) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var wanted = step.fill !== undefined ? step.fill : step.click;
    var found = null;
    doc.querySelectorAll(step.fill !== undefined ? FIELDS : CONTROLS).forEach(function (element) {
      if (found || !visible(element, view)) { return; }
      var name = accessibleName(element, doc);
      var matches = step.fill !== undefined ? name.indexOf(wanted) >= 0
                                            : (name === wanted || name.indexOf(wanted) === 0);
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

  var walked = {ok: true, start: null, steps: []};
  function finish() { out.textContent = JSON.stringify(walked); }

  var frame = document.createElement('iframe');
  frame.style.cssText = 'border:0;display:block;width:' + width + 'px;height:' + height + 'px';
  holder.appendChild(frame);

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
    if (!target) {
      walked.steps.push({found: false, page: read(frame)});
      finish();
      return;
    }
    if (step.fill !== undefined) { fill(target, step.value); } else { target.click(); }
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
