const test = require('node:test');
const assert = require('node:assert/strict');
const { add } = require(process.env.WESTACK_FIXTURE);
test('positive operands', () => assert.equal(add(2, 3), 5));
test('mixed signs', () => assert.equal(add(-2, 3), 1));

