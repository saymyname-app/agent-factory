import { expect, test } from 'vitest';
import { add } from './add';

test('add combines two numbers', () => {
  expect(add(2, 3)).toBe(5);
});
