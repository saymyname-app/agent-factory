// The measuring page of the criterion tests of the destination « Vue
// d’ensemble » (home_destination.py). It loads the page to measure in one
// frame per width, reads each frame once the page has settled, and writes
// what it read in the document, which `--dump-dom` prints:
//
//   {ok, frames: [{width, path, text, anchors, texts, nav, controls,
//                  overflow, clipped, overlaps, contrast, background,
//                  after}]}
//
// anchors   every element carrying data-anchor: name, element, and the
//           anchors that hold it, nearest first
// texts     the rendered text of each anchor
// nav       the entries of the navigation: label, current or not
// controls  every control a person can reach (link, button, field,
//           summary, an element with a role of control or a tabindex):
//           its accessible name, disabled or not, reachable by the
//           keyboard or not, and whether focusing it changes its outline,
//           shadow, border or background (a visible focus)
// overflow  how far the document is wider than the frame
// clipped   texts cut by a box that hides what overflows it, or pushed out
//           of the frame, outside any box that scrolls
// overlaps  two texts drawn on each other
// contrast  texts whose contrast with their background is under 4.5:1
//           (3:1 when large), disabled controls apart
// background the relative luminance of the page's background
// after     with `click`: the frame read again (the same record, its
//           address and text included) two seconds after the control named
//           `click` was activated, with `found` and `disabled` for that
//           control
(function () {
  var query = new URLSearchParams(location.search);
  var out = document.getElementById('measure');
  var holder = document.getElementById('frames');
  var widths = query.get('widths').split(',').map(Number);
  var height = Number(query.get('height'));
  var click = query.get('click');
  var SETTLE_MS = 2500;

  function visible(element, view) {
    if (!element.getClientRects().length) { return false; }
    // What a closed <details> holds is not drawn, its summary apart.
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
        var target = doc.getElementById(id); return target ? target.textContent : '';
      }).join(' ').trim();
      if (named) { return named; }
    }
    if (element.labels && element.labels.length) {
      var labelled = Array.prototype.map.call(element.labels, function (l) { return l.textContent; }).join(' ').trim();
      if (labelled) { return labelled; }
    }
    var text = (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim();
    if (text) { return text; }
    var img = element.querySelector('img[alt], svg[aria-label]');
    if (img) { return (img.getAttribute('alt') || img.getAttribute('aria-label') || '').trim(); }
    return (element.getAttribute('title') || element.getAttribute('placeholder') || element.value || '').toString().trim();
  }

  var CONTROLS = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [tabindex], ' +
    '[role=button], [role=link], [role=tab], [role=menuitem], [role=checkbox], [role=switch], [contenteditable=true]';

  function focusStyle(element, view) {
    var s = view.getComputedStyle(element);
    return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow, s.borderColor, s.backgroundColor,
            s.textDecorationLine].join('|');
  }

  function controls(doc, view) {
    var found = [];
    doc.querySelectorAll(CONTROLS).forEach(function (element) {
      if (!visible(element, view)) { return; }
      var disabled = element.disabled === true || element.getAttribute('aria-disabled') === 'true';
      var before = focusStyle(element, view);
      var focused = false, after = before, outline = view.getComputedStyle(element).outlineStyle;
      if (!element.disabled) {
        try { element.focus({focusVisible: true, preventScroll: true}); } catch (e) { element.focus(); }
        focused = doc.activeElement === element;
        if (focused) {
          var s = view.getComputedStyle(element);
          after = focusStyle(element, view);
          outline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 1 ? s.outlineStyle : 'none';
        }
        element.blur();
      }
      var anchorHolder = element.closest('[data-anchor]');
      found.push({
        tag: element.tagName.toLowerCase(),
        anchor: anchorHolder ? anchorHolder.getAttribute('data-anchor') : null,
        name: accessibleName(element, doc),
        disabled: disabled,
        reachable: !element.disabled && element.tabIndex >= 0,
        focused: focused,
        focus_visible: focused && (after !== before || outline !== 'none')
      });
    });
    return found;
  }

  function textRects(doc, view) {
    // One record per text node drawn: its element and its line boxes.
    var records = [];
    var walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
    var node;
    while ((node = walker.nextNode())) {
      if (!node.nodeValue.trim()) { continue; }
      var element = node.parentElement;
      if (!element || element.closest('svg, script, style, noscript, template')) { continue; }
      if (!visible(element, view)) { continue; }
      var style = view.getComputedStyle(element);
      if (style.clip !== 'auto' || style.clipPath !== 'none') { continue; }  // text meant for screen readers only
      var range = doc.createRange();
      range.selectNodeContents(node);
      var rects = Array.prototype.filter.call(range.getClientRects(), function (r) { return r.width > 1 && r.height > 1; });
      if (rects.length) { records.push({element: element, node: node, rects: rects}); }
    }
    return records;
  }

  function describe(element) {
    var anchorHolder = element.closest('[data-anchor]');
    var text = (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80);
    return (anchorHolder ? anchorHolder.getAttribute('data-anchor') : element.tagName.toLowerCase()) + ' « ' + text + ' »';
  }

  function clipped(records, view, width) {
    var cut = [];
    records.forEach(function (record) {
      var element = record.element, reason = null;
      var style = view.getComputedStyle(element);
      if (style.textOverflow === 'ellipsis' && element.scrollWidth > element.clientWidth + 1) {
        reason = 'coupé par des points de suspension';
      }
      record.rects.forEach(function (rect) {
        if (reason) { return; }
        var scrolls = false;
        for (var up = element; up && up !== record.node.ownerDocument.documentElement; up = up.parentElement) {
          var s = view.getComputedStyle(up);
          var scrollX = s.overflowX === 'auto' || s.overflowX === 'scroll';
          var scrollY = s.overflowY === 'auto' || s.overflowY === 'scroll';
          if (scrollX || scrollY) { scrolls = true; }
          var hidesX = s.overflowX === 'hidden' || s.overflowX === 'clip';
          var hidesY = s.overflowY === 'hidden' || s.overflowY === 'clip';
          if (hidesX || hidesY) {
            var box = up.getBoundingClientRect();
            if ((hidesX && (rect.left < box.left - 1 || rect.right > box.right + 1)) ||
                (hidesY && (rect.top < box.top - 1 || rect.bottom > box.bottom + 1))) {
              reason = 'coupé par ' + describe(up).slice(0, 40); return;
            }
          }
        }
        if (!scrolls && (rect.left < -1 || rect.right > width + 1)) { reason = 'hors du cadre de ' + width + ' px'; }
      });
      if (reason) { cut.push(describe(element) + ' : ' + reason); }
    });
    return cut;
  }

  function pinned(element, view) {
    for (var up = element; up; up = up.parentElement) {
      var position = view.getComputedStyle(up).position;
      if (position === 'fixed' || position === 'sticky') { return true; }
    }
    return false;
  }

  function overlaps(records, view) {
    var found = [];
    var free = records.filter(function (r) { return !pinned(r.element, view); });
    for (var i = 0; i < free.length; i++) {
      for (var j = i + 1; j < free.length; j++) {
        var a = free[i], b = free[j];
        if (a.element === b.element || a.element.contains(b.element) || b.element.contains(a.element)) { continue; }
        var hit = a.rects.some(function (ra) {
          return b.rects.some(function (rb) {
            var w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
            var h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
            return w > 2 && h > 2;
          });
        });
        if (hit) { found.push(describe(a.element) + ' sur ' + describe(b.element)); }
      }
    }
    return found;
  }

  function rgba(value) {
    var m = value.match(/rgba?\(([^)]+)\)/);
    if (!m) { return null; }
    var p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  }

  function over(top, bottom) {
    var a = top.a + bottom.a * (1 - top.a);
    if (a === 0) { return {r: 0, g: 0, b: 0, a: 0}; }
    return {
      r: (top.r * top.a + bottom.r * bottom.a * (1 - top.a)) / a,
      g: (top.g * top.a + bottom.g * bottom.a * (1 - top.a)) / a,
      b: (top.b * top.a + bottom.b * bottom.a * (1 - top.a)) / a, a: a
    };
  }

  function luminance(c) {
    function channel(v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
    return 0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b);
  }

  // The colour drawn behind an element, or null when an image or a
  // gradient is drawn there (its contrast is not computed).
  function backgroundOf(element, view, doc) {
    var layers = [];
    for (var up = element; up; up = up.parentElement) {
      var s = view.getComputedStyle(up);
      if (s.backgroundImage && s.backgroundImage !== 'none') { return null; }
      var c = rgba(s.backgroundColor);
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) { break; } }
    }
    var scheme = view.getComputedStyle(doc.documentElement).colorScheme || '';
    var canvas = /dark/.test(scheme) && !/light/.test(scheme) ? {r: 18, g: 18, b: 18, a: 1} : {r: 255, g: 255, b: 255, a: 1};
    var colour = canvas;
    for (var i = layers.length - 1; i >= 0; i--) { colour = over(layers[i], colour); }
    return colour;
  }

  function contrast(records, view, doc) {
    var low = [];
    records.forEach(function (record) {
      var element = record.element;
      if (element.closest('[disabled], [aria-disabled=true]')) { return; }
      var s = view.getComputedStyle(element);
      var fg = rgba(s.color), bg = backgroundOf(element, view, doc);
      if (!fg || !bg) { return; }
      fg = over({r: fg.r, g: fg.g, b: fg.b, a: fg.a * Number(s.opacity || 1)}, bg);
      var l1 = luminance(fg), l2 = luminance(bg);
      var ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      var size = parseFloat(s.fontSize), bold = Number(s.fontWeight) >= 700;
      var needed = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
      if (ratio < needed - 0.01) { low.push(describe(element) + ' : ' + ratio.toFixed(2) + ':1'); }
    });
    return low;
  }

  function read(frame, width) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var anchors = [], texts = {};
    doc.querySelectorAll('[data-anchor]').forEach(function (element) {
      var chain = [];
      for (var up = element.parentElement; up; up = up.parentElement) {
        if (up.hasAttribute('data-anchor')) { chain.push(up.getAttribute('data-anchor')); }
      }
      var name = element.getAttribute('data-anchor');
      anchors.push({name: name, tag: element.tagName.toLowerCase(), chain: chain});
      texts[name] = (element.innerText || element.textContent || '').split('\n').map(function (l) { return l.trim(); })
        .filter(Boolean).join('\n');
    });
    var nav = [];
    doc.querySelectorAll('nav a, nav button, nav [role=link], nav [role=tab]').forEach(function (element) {
      nav.push({
        label: (element.innerText || '').split('\n')[0].trim(),
        current: element.getAttribute('aria-current') === 'page' || element.getAttribute('aria-selected') === 'true'
      });
    });
    var records = textRects(doc, view);
    var bg = backgroundOf(doc.body, view, doc);
    var measured = {
      width: width, path: view.location.pathname,
      text: doc.body ? doc.body.innerText : '',
      anchors: anchors, texts: texts, nav: nav,
      overflow: Math.max(0, doc.documentElement.scrollWidth - view.innerWidth),
      clipped: clipped(records, view, width),
      overlaps: overlaps(records, view),
      contrast: contrast(records, view, doc),
      background: bg ? luminance(bg) : null
    };
    measured.controls = controls(doc, view);
    return measured;
  }

  function activate(frame, name, done) {
    var doc = frame.contentDocument;
    var target = null;
    doc.querySelectorAll(CONTROLS).forEach(function (element) {
      // A name followed by what the control adds (a count, an arrow) is
      // the same control: « Vue d’ensemble 2 », « Essai ↗ ».
      var own = accessibleName(element, doc);
      if (!target && visible(element, frame.contentWindow) && (own === name || own.indexOf(name) === 0)) { target = element; }
    });
    if (!target) {
      done({found: false, path: frame.contentWindow.location.pathname, text: doc.body.innerText,
            anchors: [], texts: {}, nav: [], controls: []});
      return;
    }
    var finished = false;
    function report() {
      if (finished) { return; }
      finished = true;
      var d = frame.contentDocument, page;
      try { page = read(frame, Number(frame.style.width.replace('px', ''))); } catch (error) {
        page = {path: frame.contentWindow.location.pathname, text: d && d.body ? d.body.innerText : '',
                anchors: [], texts: {}, nav: [], controls: []};
      }
      page.found = true;
      page.disabled = target.disabled === true || target.getAttribute('aria-disabled') === 'true';
      done(page);
    }
    frame.addEventListener('load', function () { setTimeout(report, SETTLE_MS); }, {once: true});
    target.click();
    setTimeout(report, SETTLE_MS + 1500);
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
        try {
          results[index] = read(frame, width);
        } catch (error) {
          out.textContent = JSON.stringify({ok: false, error: String(error)});
          return;
        }
        if (!click) { finish(); return; }
        activate(frame, click, function (after) { results[index].after = after; finish(); });
      }, SETTLE_MS);
    }, {once: true});
    frame.src = query.get('target');
  });
})();
