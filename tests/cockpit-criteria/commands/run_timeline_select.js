// The selecting page of the criterion tests of the run timeline
// (run_timeline.py). It loads the page to read in one frame of the given
// width, activates in it the control of a job -- the control whose text
// says the title of that job --, then reads the frame two seconds later;
// with `reload`, it reloads the frame and reads it once more. It writes
// what it read in the document, which `--dump-dom` prints:
//
//   {ok, selected: reading, reloaded: reading or null}
//
// A reading holds:
//
// Both are looked for in the timeline (the anchor `chart`), or in the
// whole page when it has none: a detail drawn under the timeline is not
// the timeline.
//
// found      whether a control saying the title was found
// path       the path of the frame's address
// marked     the texts of what the timeline marks as selected: an element with aria-pressed="true",
//            aria-selected="true", or an aria-current other than "false"
// target     whether that control, or what holds it, is marked so
// visible    the part of the control a person sees in the frame:
//            {width, height} of what is left of its box once cut by the
//            frame and by every box around it that scrolls or hides what
//            overflows it
// box        {width, height} of the control's box
// local      whether a box around the control scrolls across on its own:
//            its content is wider than it and it scrolls (auto, scroll)
// overflow   how far the document is wider than the frame
(function () {
  var query = new URLSearchParams(location.search);
  var out = document.getElementById('measure');
  var holder = document.getElementById('frames');
  var width = Number(query.get('width'));
  var height = Number(query.get('height'));
  var title = query.get('title');
  var keys = query.get('keys') === '1';
  var reload = query.get('reload') === '1';
  var SETTLE_MS = 2500;
  var CONTROLS = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [tabindex], ' +
    '[role=button], [role=link], [role=tab], [role=menuitem], [role=checkbox], [role=switch]';
  var NATIVE = 'a[href], button, input:not([type=hidden]), select, textarea, summary';
  var MARKED = '[aria-pressed="true"], [aria-selected="true"], [aria-current]:not([aria-current="false"])';

  function said(element) {
    return (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function timeline(doc) { return doc.querySelector('[data-anchor="chart"]') || doc.body; }

  // The control of the timeline saying `title` that says the least
  // besides: the job's own control, not a box holding several jobs.
  function control(doc) {
    var best = null;
    timeline(doc).querySelectorAll(CONTROLS).forEach(function (element) {
      if (!element.getClientRects().length || element.closest('nav')) { return; }
      var text = said(element);
      if (text.indexOf(title) < 0) { return; }
      if (!best || text.length < said(best).length) { best = element; }
    });
    return best;
  }

  function hides(value) { return /auto|scroll|hidden|clip/.test(value); }

  function reading(frame) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var found = control(doc);
    var marked = [];
    timeline(doc).querySelectorAll(MARKED).forEach(function (element) {
      if (!element.closest('nav')) { marked.push(said(element)); }
    });
    var record = {found: !!found, path: view.location.pathname, marked: marked, target: false,
                  visible: {width: 0, height: 0}, box: {width: 0, height: 0}, local: false,
                  overflow: Math.max(0, doc.documentElement.scrollWidth - view.innerWidth)};
    if (!found) { return record; }
    record.target = !!(found.matches(MARKED) || found.closest(MARKED));
    var box = found.getBoundingClientRect();
    record.box = {width: box.width, height: box.height};
    var left = Math.max(box.left, 0), right = Math.min(box.right, view.innerWidth);
    var top = box.top, bottom = box.bottom;
    for (var up = found.parentElement; up && up !== doc.body && up !== doc.documentElement; up = up.parentElement) {
      var style = view.getComputedStyle(up), around = up.getBoundingClientRect();
      var inLeft = around.left + up.clientLeft, inTop = around.top + up.clientTop;
      if (hides(style.overflowX)) {
        left = Math.max(left, inLeft);
        right = Math.min(right, inLeft + up.clientWidth);
        if (/auto|scroll/.test(style.overflowX) && up.scrollWidth > up.clientWidth + 1) { record.local = true; }
      }
      if (hides(style.overflowY)) {
        top = Math.max(top, inTop);
        bottom = Math.min(bottom, inTop + up.clientHeight);
      }
    }
    record.visible = {width: Math.max(0, right - left), height: Math.max(0, bottom - top)};
    return record;
  }

  // Enter pressed on `target`, focused: what a script does of the key,
  // then, when nothing prevented it, what the browser does of it on a
  // control of its own.
  function press(target) {
    var view = target.ownerDocument.defaultView;
    target.focus();
    var options = {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true};
    var handled = !target.dispatchEvent(new view.KeyboardEvent('keydown', options));
    target.dispatchEvent(new view.KeyboardEvent('keyup', options));
    if (!handled && target.matches(NATIVE) && !target.disabled) { target.click(); }
  }

  // `then(reading)` once the frame settled after `act` -- a new document
  // loaded by it, or the same one changed.
  function after(frame, act, then) {
    var done = false;
    function report() {
      if (done) { return; }
      done = true;
      try { then(reading(frame)); } catch (error) { fail(error); }
    }
    frame.addEventListener('load', function () { setTimeout(report, SETTLE_MS); }, {once: true});
    act();
    setTimeout(report, SETTLE_MS + 1500);
  }

  function fail(error) { out.textContent = JSON.stringify({ok: false, error: String(error)}); }

  var frame = document.createElement('iframe');
  frame.style.cssText = 'border:0;display:block;width:' + width + 'px;height:' + height + 'px';
  holder.appendChild(frame);
  frame.addEventListener('load', function () {
    setTimeout(function () {
      var target;
      try { target = control(frame.contentDocument); } catch (error) { fail(error); return; }
      if (!target) {
        out.textContent = JSON.stringify({ok: true, selected: reading(frame), reloaded: null});
        return;
      }
      after(frame, function () { if (keys) { press(target); } else { target.click(); } }, function (selected) {
        if (!reload) {
          out.textContent = JSON.stringify({ok: true, selected: selected, reloaded: null});
          return;
        }
        after(frame, function () { frame.contentWindow.location.reload(); }, function (reloaded) {
          out.textContent = JSON.stringify({ok: true, selected: selected, reloaded: reloaded});
        });
      });
    }, SETTLE_MS);
  }, {once: true});
  frame.src = query.get('target');
})();
