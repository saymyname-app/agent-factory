#!/usr/bin/env node
// Source-level design checks, using the TypeScript parser already pinned by the code defaults.
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const pattern = /#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|oklch)\s*\(|(?<![\w.-])\d+(?:\.\d+)?(?:px|rem|em|vh|vw|vmin|vmax|%|ms|s)\b/i;
const visibleAttributes = new Set(['alt', 'title', 'placeholder', 'aria-label', 'aria-description', 'label', 'helperText', 'description', 'tooltip']);
const errors = [];
function visitFiles(dir) {
  if (!fs.existsSync(dir)) return;
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, item.name);
    if (item.isDirectory()) visitFiles(file);
    else if (/\.(tsx|jsx|ts|js)$/.test(file) && !file.startsWith('src/theme/')) check(file);
  }
}
function check(file) {
  const source = fs.readFileSync(file, 'utf8');
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true,
    /\.[jt]sx$/.test(file) ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  function report(node, message) {
    const line = tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1;
    errors.push(`${file}:${line}: ${message}`);
  }
  function attribute(node, name) {
    return node.attributes.properties.find(item => ts.isJsxAttribute(item) && item.name.text === name);
  }
  function associatedLabel(node) {
    for (let parent = node.parent; parent; parent = parent.parent) {
      if (ts.isJsxElement(parent) && parent.openingElement.tagName.getText(tree) === 'label') return true;
    }
    const id = attribute(node, 'id')?.initializer;
    if (!id || !ts.isStringLiteral(id)) return false;
    let found = false;
    function find(label) {
      if (ts.isJsxOpeningElement(label) && label.tagName.getText(tree) === 'label' &&
        attribute(label, 'htmlFor')?.initializer?.text === id.text) found = true;
      if (!found) ts.forEachChild(label, find);
    }
    find(tree);
    return found;
  }
  function walk(node) {
    if (ts.isStringLiteral(node) && pattern.test(node.text)) report(node, 'valeur de design en dur hors du thème');
    if (ts.isNoSubstitutionTemplateLiteral(node) && pattern.test(node.text)) report(node, 'valeur de design en dur hors du thème');
    if (ts.isJsxText(node) && node.getText(tree).trim()) report(node, 'texte affiché en dur');
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      let parent = node.parent;
      while (parent && !ts.isSourceFile(parent)) {
        if (ts.isCallExpression(parent) && (parent.expression.getText(tree) === 't' ||
          parent.expression.getText(tree) === 'i18n.t')) break;
        if (ts.isJsxAttribute(parent) && visibleAttributes.has(parent.name.text) &&
          !ts.isStringLiteral(parent.initializer)) {
          report(node, `texte ${parent.name.text} en dur`);
          break;
        }
        if (ts.isJsxExpression(parent) && !ts.isJsxAttribute(parent.parent)) {
          report(node, 'texte affiché en dur');
          break;
        }
        parent = parent.parent;
      }
    }
    if (ts.isJsxAttribute(node) && ['style', 'sx'].includes(node.name.text)) report(node, 'style inline interdit : utiliser les tokens du thème');
    if (ts.isJsxAttribute(node) && visibleAttributes.has(node.name.text) && node.initializer && ts.isStringLiteral(node.initializer)) {
      report(node, `texte ${node.name.text} en dur`);
    }
    if ((ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) && node.tagName.getText(tree) === 'img') {
      if (!node.attributes.properties.some(attribute => ts.isJsxAttribute(attribute) && attribute.name.text === 'alt')) report(node, 'image sans alt');
    }
    if ((ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) && ['div', 'span'].includes(node.tagName.getText(tree))) {
      if (node.attributes.properties.some(attribute => ts.isJsxAttribute(attribute) && attribute.name.text === 'onClick')) report(node, 'clic sur élément non interactif');
    }
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const tag = node.tagName.getText(tree);
      const named = node.attributes.properties.some(attribute => ts.isJsxAttribute(attribute) &&
        ['aria-label', 'aria-labelledby'].includes(attribute.name.text));
      if (tag === 'input' && !named && !associatedLabel(node)) report(node, 'champ sans libellé accessible');
      if (tag === 'button' && !named) {
        const parent = ts.isJsxOpeningElement(node) ? node.parent : null;
        const hasChildren = parent && ts.isJsxElement(parent) && parent.children.some(child =>
          !ts.isJsxText(child) || child.getText(tree).trim());
        if (!hasChildren) report(node, 'bouton sans nom accessible');
      }
    }
    ts.forEachChild(node, walk);
  }
  walk(tree);
}
visitFiles('src');
for (const error of errors) console.error(error);
if (errors.length) process.exitCode = 1;
