// The measuring page of the criterion tests of the destination « Vue
// d’ensemble » (home_destination.py). It loads the page to measure in one
// frame per width, reads each frame once the page has settled, and writes
// what it read in the document, which `--dump-dom` prints:
//
//   {ok, frames: [{width, path, text, anchors, texts, nav, controls,
//                  overflow, clipped, overlaps, contrast, background,
//                  after}]}
//
// anchors   every element carrying data-anchor: name, element, the
//           anchors that hold it, nearest first, and its computed
//           font-family and line-height (`styles`)
// texts     the rendered text of each anchor; of a frame (an iframe
//           carrying data-anchor), the text of the document it shows
// inside    for each frame carrying data-anchor, what the document it
//           shows holds: its anchors (name, element, chain, text on one
//           line), and its
//           height against the frame's (`content_height`, `height`); its
//           texts and controls are read with the page's, under the
//           clipped, overlaps, contrast and controls below
// nav       the entries of the navigation: label, current or not
// controls  every control a person can reach (link, button, field,
//           summary, an element with a role of control or a tabindex):
//           its accessible name, disabled or not, reachable by the
//           keyboard or not, and whether focusing it draws a focus a
//           person sees (`focus_visible`): an outline, a shadow, a border
//           that focusing adds or changes, at 3:1 at least against what is
//           behind the control (its border against the border it had), a
//           background that changes at 3:1 at least, or an underline added
//           -- another change of style is not a focus one sees; `native`, a
//           control the browser itself activates with the keyboard (a link,
//           a button, a field, a summary) -- any other one is activated by
//           a script, or not at all; `state`, its aria-current,
//           aria-selected and aria-pressed; `shape`, how it is drawn without
//           its colours (borders, shadows, outline, weight, decoration);
//           `boundary`, for a button or a field drawn as a box (a border on
//           its four sides), the contrast of that box with what is behind
//           it: the larger of its border's and its fill's
// overflow  how far the document is wider than the frame
// clipped   texts cut by a box that hides what overflows it, or pushed out
//           of the frame, outside any box that scrolls
// overlaps  two texts drawn on each other, wherever they are placed
// contrast  texts whose contrast with their background is under 4.5:1
//           (3:1 when large), disabled controls apart
// background the relative luminance of the page's background
// scrolls   every box that scrolls on its own (overflow auto or scroll, or
//           a frame) whose content is larger than it: `name`, whether its
//           content can be scrolled into view (`scrolls`: a frame whose
//           document hides what overflows it cannot) and whether the
//           keyboard reaches it or a control inside it (`keyboard`)
// after     with `click`: the frame read again (the same record, its
//           address and text included) two seconds after the control named
//           `click` was activated, with `found` and `disabled` for that
//           control; with `keys` too, activated by the keyboard -- focused,
//           then Enter pressed on it -- rather than by a click
// readings  the frame as first read, then read again after each of
//           `steps` (a JSON list) was played: {click, within, keys}
//           activates the control drawn inside the anchor `within` (the
//           page when none) whose accessible name is or starts with
//           `click`, else the first that holds it; {wait: ms} waits;
//           {reload: true} reloads the page. Each reading after a step
//           carries `step`: what it did, `found` false when the control it
//           names is not on the page
//
// Each anchor also holds whether it is drawn (`drawn`), its rendered text
// on one line (`text`, empty when not drawn) and its whole text, a closed
// section included (`content`), whether it is open (a <details>), its box
// in the page (`box`) and the colours it is drawn with (`colours`: its
// text, its background, its left border, what its ::before and ::after
// draw); each frame its address (`href`, path and query) and the dialogs
// drawn (`dialogs`); each scrolling box the anchor that holds it (`anchor`).
(function () {
  var query = new URLSearchParams(location.search);
  var out = document.getElementById('measure');
  var holder = document.getElementById('frames');
  var widths = query.get('widths').split(',').map(Number);
  var height = Number(query.get('height'));
  var click = query.get('click');
  var keys = query.get('keys') === '1';
  var steps = JSON.parse(query.get('steps') || '[]');
  var SETTLE_MS = 2500;
  var CONTENT_LIMIT = 6000;

  function line(text) { return (text || '').replace(/\s+/g, ' ').trim(); }

  function painted(value) {
    return value && value !== 'transparent' && !/rgba\([^)]*,\s*0\)$/.test(value) ? value : null;
  }

  // The colours an element is drawn with: its text, its background, its
  // left border when it is drawn, and what its ::before and ::after draw.
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
  // The controls the browser activates by itself when Enter is pressed on
  // them.
  var NATIVE = 'a[href], button, input:not([type=hidden]), select, textarea, summary';
  var BOXED = 'button, input:not([type=hidden]), select, textarea';

  function focusStyle(element, view) {
    var s = view.getComputedStyle(element);
    return {outline: [s.outlineStyle, s.outlineWidth, s.outlineColor].join('|'), outlineStyle: s.outlineStyle,
            outlineWidth: s.outlineWidth, outlineColor: s.outlineColor, boxShadow: s.boxShadow,
            borderColor: s.borderTopColor, borderWidth: s.borderTopWidth, borderStyle: s.borderTopStyle,
            textDecorationLine: s.textDecorationLine};
  }

  // Whether the style `after` the control was focused draws a focus a
  // person sees, against the style `before` and what is behind it.
  function focusSeen(element, before, after, fillBefore, fillAfter, view, doc) {
    var behind = backgroundOf(element.parentElement || element, view, doc);
    if (!behind) { return true; }  // an image or a gradient behind: not computed
    var seen = function (colour) { var c = rgba(colour); return c && c.a > 0 && ratio(over(c, behind), behind) >= 3; };
    if (after.outline !== before.outline && after.outlineStyle !== 'none' && parseFloat(after.outlineWidth) >= 1 &&
        seen(after.outlineColor)) { return true; }
    if (after.boxShadow !== before.boxShadow && after.boxShadow !== 'none' && seen(after.boxShadow)) { return true; }
    if (after.borderColor !== before.borderColor && parseFloat(after.borderWidth) >= 1 && after.borderStyle !== 'none') {
      var was = rgba(before.borderColor), is = rgba(after.borderColor);
      if (was && is && ratio(over(is, behind), over(was, behind)) >= 3) { return true; }
    }
    if (fillBefore && fillAfter && ratio(fillAfter, fillBefore) >= 3) { return true; }
    return after.textDecorationLine !== before.textDecorationLine && /underline/.test(after.textDecorationLine);
  }

  function controls(doc, view) {
    var found = [];
    doc.querySelectorAll(CONTROLS).forEach(function (element) {
      if (!visible(element, view)) { return; }
      var disabled = element.disabled === true || element.getAttribute('aria-disabled') === 'true';
      var before = focusStyle(element, view), fillBefore = backgroundOf(element, view, doc);
      var focused = false, seen = false;
      if (!element.disabled) {
        try { element.focus({focusVisible: true, preventScroll: true}); } catch (e) { element.focus(); }
        focused = doc.activeElement === element;
        if (focused) {
          seen = focusSeen(element, before, focusStyle(element, view), fillBefore, backgroundOf(element, view, doc),
                           view, doc);
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
        focus_visible: focused && seen,
        native: element.matches(NATIVE),
        state: {current: element.getAttribute('aria-current'), selected: element.getAttribute('aria-selected'),
                pressed: element.getAttribute('aria-pressed')},
        shape: shape(element, view),
        boundary: disabled ? null : boundary(element, view, doc)
      });
    });
    return found;
  }

  function shape(element, view) {
    var s = view.getComputedStyle(element);
    var colourless = function (value) { return value.replace(/rgba?\([^)]*\)/g, ''); };
    return [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth,
            s.borderTopStyle, s.borderRightStyle, s.borderBottomStyle, s.borderLeftStyle,
            colourless(s.boxShadow), s.outlineStyle, s.outlineWidth, s.fontWeight, s.textDecorationLine].join('|');
  }

  function ratio(a, b) {
    var l1 = luminance(a), l2 = luminance(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }

  function boundary(element, view, doc) {
    if (!element.matches(BOXED)) { return null; }
    var s = view.getComputedStyle(element);
    var sides = ['Top', 'Right', 'Bottom', 'Left'];
    var boxed = sides.every(function (side) {
      var colour = rgba(s['border' + side + 'Color']);
      return parseFloat(s['border' + side + 'Width']) >= 1 && s['border' + side + 'Style'] !== 'none' &&
        colour && colour.a > 0;
    });
    if (!boxed) { return null; }
    var behind = element.parentElement ? backgroundOf(element.parentElement, view, doc) : null;
    var fill = backgroundOf(element, view, doc);
    if (!behind || !fill) { return null; }
    var border = rgba(s.borderTopColor);
    return Math.max(ratio(over(border, behind), behind), ratio(fill, behind));
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

  function overlaps(records) {
    var found = [];
    for (var i = 0; i < records.length; i++) {
      for (var j = i + 1; j < records.length; j++) {
        var a = records[i], b = records[j];
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
      var name = element.getAttribute('data-anchor'), computed = view.getComputedStyle(element);
      var box = element.getBoundingClientRect(), shown = visible(element, view);
      anchors.push({name: name, tag: element.tagName.toLowerCase(), chain: chain, styles: {
        'font-family': computed.getPropertyValue('font-family'),
        'line-height': computed.getPropertyValue('line-height')
      }, drawn: shown, text: shown ? line(element.innerText).slice(0, CONTENT_LIMIT) : '',
        content: line(element.textContent).slice(0, CONTENT_LIMIT),
        open: element.tagName === 'DETAILS' ? element.open : null,
        box: {top: box.top + view.scrollY, bottom: box.bottom + view.scrollY, left: box.left, right: box.right,
              width: box.width, height: box.height},
        colours: colours(element, view)});
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
    var dialogs = [];
    doc.querySelectorAll('dialog[open], [role=dialog], [role=alertdialog], [aria-modal=true]').forEach(function (element) {
      if (visible(element, view)) { dialogs.push(line(accessibleName(element, doc)).slice(0, 80)); }
    });
    var measured = {
      width: width, path: view.location.pathname, href: view.location.pathname + view.location.search,
      dialogs: dialogs,
      text: doc.body ? doc.body.innerText : '',
      anchors: anchors, texts: texts, nav: nav, inside: {},
      overflow: Math.max(0, doc.documentElement.scrollWidth - view.innerWidth),
      clipped: clipped(records, view, width),
      overlaps: overlaps(records),
      contrast: contrast(records, view, doc),
      background: bg ? luminance(bg) : null,
      scrolls: scrolls(doc, view)
    };
    measured.controls = controls(doc, view);
    // The documents the frames of the page show: their texts and controls
    // are the page's too.
    doc.querySelectorAll('iframe[data-anchor]').forEach(function (frame) {
      var name = frame.getAttribute('data-anchor'), inner = null;
      try { inner = frame.contentDocument; } catch (error) { inner = null; }
      if (!inner || !inner.body || !visible(frame, view)) { measured.inside[name] = null; return; }
      var innerView = frame.contentWindow, innerAnchors = [];
      inner.querySelectorAll('[data-anchor]').forEach(function (element) {
        var chain = [];
        for (var up = element.parentElement; up; up = up.parentElement) {
          if (up.hasAttribute('data-anchor')) { chain.push(up.getAttribute('data-anchor')); }
        }
        innerAnchors.push({name: element.getAttribute('data-anchor'), tag: element.tagName.toLowerCase(), chain: chain,
                           text: (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim()});
      });
      texts[name] = (inner.body.innerText || '').split('\n').map(function (l) { return l.trim(); })
        .filter(Boolean).join('\n');
      var contentHeight = inner.documentElement.scrollHeight, height = innerView.innerHeight;
      measured.inside[name] = {anchors: innerAnchors, height: height, content_height: contentHeight};
      var innerRecords = textRects(inner, innerView);
      var mark = function (line) { return name + ' › ' + line; };
      measured.clipped = measured.clipped.concat(clipped(innerRecords, innerView, innerView.innerWidth).map(mark));
      measured.overlaps = measured.overlaps.concat(overlaps(innerRecords).map(mark));
      measured.contrast = measured.contrast.concat(contrast(innerRecords, innerView, inner).map(mark));
      measured.controls = measured.controls.concat(controls(inner, innerView).map(function (control) {
        control.frame = name; return control;
      }));
      measured.scrolls = measured.scrolls.concat(scrolls(inner, innerView).map(function (box) {
        box.name = mark(box.name); return box;
      }));
      if (contentHeight > height + 1) {
        var root = innerView.getComputedStyle(inner.documentElement), body = innerView.getComputedStyle(inner.body);
        var hides = frame.getAttribute('scrolling') === 'no' || /hidden|clip/.test(root.overflowY) ||
          /hidden|clip/.test(body.overflowY);
        measured.scrolls.push({name: name, scrolls: !hides,
                               keyboard: !!inner.querySelector(CONTROLS) || frame.tabIndex >= 0});
      }
    });
    return measured;
  }

  // The boxes of a document that scroll on their own and whose content is
  // larger than them (the document itself apart: its overflow is `overflow`).
  function scrolls(doc, view) {
    var found = [];
    doc.querySelectorAll('body *').forEach(function (element) {
      if (!visible(element, view)) { return; }
      var s = view.getComputedStyle(element);
      var x = /auto|scroll/.test(s.overflowX) && element.scrollWidth > element.clientWidth + 1;
      var y = /auto|scroll/.test(s.overflowY) && element.scrollHeight > element.clientHeight + 1;
      if (x || y) {
        var holding = element.closest('[data-anchor]');
        found.push({name: describe(element).slice(0, 60), scrolls: true,
                    anchor: holding ? holding.getAttribute('data-anchor') : null,
                    keyboard: element.tabIndex >= 0 || !!element.querySelector(CONTROLS)});
      }
    });
    return found;
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
    if (!keys) { target.click(); } else { press(target); }
    setTimeout(report, SETTLE_MS + 1500);
  }

  // Enter pressed on `target`, focused: what a script does of the key, then,
  // when nothing prevented it, what the browser does of it by itself on a
  // control of its own (HTML: Enter on a link or a button activates it) --
  // on another element, nothing.
  function press(target) {
    var view = target.ownerDocument.defaultView;
    target.focus();
    var options = {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true};
    var down = new view.KeyboardEvent('keydown', options);
    var handled = !target.dispatchEvent(down);
    target.dispatchEvent(new view.KeyboardEvent('keyup', options));
    if (!handled && target.matches(NATIVE) && !target.disabled) { target.click(); }
  }

  // The control drawn inside the anchor `within` (the page when none) whose
  // accessible name is or starts with `name`, else the first that holds it.
  function control(frame, name, within) {
    var doc = frame.contentDocument, view = frame.contentWindow;
    var scope = within ? doc.querySelector('[data-anchor="' + within + '"]') : doc;
    if (!scope) { return null; }
    var candidates = Array.prototype.filter.call(scope.querySelectorAll(CONTROLS), function (element) {
      return visible(element, view);
    });
    var named = function (element) { return line(accessibleName(element, doc)); };
    return candidates.find(function (element) { return named(element).indexOf(name) === 0; }) ||
      candidates.find(function (element) { return named(element).indexOf(name) >= 0; }) || null;
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
    if (step.keys) { press(target); } else { target.click(); }
    setTimeout(function () { settle({click: step.click, found: true}); }, SETTLE_MS + 1500);
  }

  // The readings of `frame` after each of `steps`, from `position` on.
  function playAll(frame, width, readings, position, done) {
    if (position >= steps.length) { done(); return; }
    play(frame, steps[position], function (what) {
      var reading;
      try { reading = read(frame, width); } catch (error) {
        reading = {width: width, href: '', path: '', text: '', anchors: [], texts: {}, nav: [], controls: [],
                   dialogs: [], scrolls: [], overflow: 0, unread: String(error)};
      }
      reading.step = what;
      readings.push(reading);
      playAll(frame, width, readings, position + 1, done);
    });
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
        var readings = [results[index]];
        results[index] = Object.assign({}, results[index], {readings: readings});
        if (steps.length) { playAll(frame, width, readings, 0, finish); return; }
        if (!click) { finish(); return; }
        activate(frame, click, function (after) { results[index].after = after; finish(); });
      }, SETTLE_MS);
    }, {once: true});
    frame.src = query.get('target');
  });
})();
